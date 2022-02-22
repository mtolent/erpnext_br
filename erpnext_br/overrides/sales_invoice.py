from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

from frappe.utils.data import flt
from erpnext.accounts.utils import get_account_currency
from erpnext.stock.get_item_details import get_item_defaults, get_item_group_defaults, get_brand_defaults

import frappe

class SalesInvoice(SalesInvoice):
	def before_save(self):
		super()
		if self.enable_accrued_income:
			for line_item in self.get("items"):
				line_item.enable_accrued_income = True
				line_item.accrued_income_date = self.accrued_income_date
				item_defaults = get_item_defaults(line_item.item_code, self.company)
				item_group_defaults = get_item_group_defaults(line_item.item_code, self.company)
				brand_defaults = get_brand_defaults(line_item.item_code, self.company)
				line_item.accrued_income_account =  (item_defaults.get("accrued_income_account")
							or item_group_defaults.get("accrued_income_account")
							or brand_defaults.get("accrued_income_account"))

	def make_item_gl_entries(self, gl_entries):
		# income account gl entries
		for item in self.get("items"):
			if flt(item.base_net_amount, item.precision("base_net_amount")):
				if item.is_fixed_asset:
					asset = self.get_asset(item)

					if self.is_return:
						fixed_asset_gl_entries = self.get_gl_entries_on_asset_regain(asset,
							item.base_net_amount, item.finance_book)
						asset.db_set("disposal_date", None)

						if asset.calculate_depreciation:
							self.reverse_depreciation_entry_made_after_sale(asset)
							self.reset_depreciation_schedule(asset)

					else:
						fixed_asset_gl_entries = self.get_gl_entries_on_asset_disposal(asset,
							item.base_net_amount, item.finance_book)
						asset.db_set("disposal_date", self.posting_date)

						if asset.calculate_depreciation:
							self.depreciate_asset(asset)

					for gle in fixed_asset_gl_entries:
						gle["against"] = self.customer
						gl_entries.append(self.get_gl_dict(gle, item=item))

					self.set_asset_status(asset)

				else:
					# Do not book income for transfer within same company
					if not self.is_internal_transfer():
						income_account = (item.income_account
							if (not item.enable_deferred_revenue or self.is_return) else item.deferred_revenue_account)

						amount, base_amount = self.get_amount_and_base_amount(item, self.enable_discount_accounting)

						account_currency = get_account_currency(income_account)

						if item.enable_accrued_income:
							journal_entry = frappe.new_doc("Journal Entry")
							journal_entry.voucher_type = "Journal Entry"
							journal_entry.user_remark = ("Accrual Journal Entry for Sales Invoice {0}")\
								.format(self.name)
							journal_entry.company = self.company
							journal_entry.posting_date = item.accrued_income_date
							
							accounts = []

							accounts.append(
								self.get_gl_dict({
									"account": income_account,
									"against": self.customer,
									"credit": flt(base_amount, item.precision("base_net_amount")),
									"credit_in_account_currency": (flt(base_amount, item.precision("base_net_amount"))
										if account_currency==self.company_currency
										else flt(amount, item.precision("net_amount"))),
									"cost_center": item.cost_center,
									"project": item.project or self.project
								}, account_currency, item=item)
							)
							income_account = item.accrued_income_account
							accounts.append(
								self.get_gl_dict({
									"posting_date": item.accrued_income_date,
									"account": income_account,
									"against": self.customer,
									"debit": flt(base_amount, item.precision("base_net_amount")),
									"debit_in_account_currency": (flt(base_amount, item.precision("base_net_amount"))
										if account_currency==self.company_currency
										else flt(amount, item.precision("net_amount"))),
									"cost_center": item.cost_center,
									"project": item.project or self.project
								}, account_currency, item=item)
							)
							journal_entry.set("accounts", accounts)
							#journal_entry.title = payroll_payable_account
							journal_entry.save()
							try:
								journal_entry.submit()
								frappe.db.set_value("Sales Invoice Item", item.name, "accrued_journal_entry", journal_entry.name)
							except Exception as e:
								if type(e) in (str, list, tuple):
									frappe.msgprint(e)
								raise

						gl_entries.append(
							self.get_gl_dict({
								"account": income_account,
								"against": self.customer,
								"credit": flt(base_amount, item.precision("base_net_amount")),
								"credit_in_account_currency": (flt(base_amount, item.precision("base_net_amount"))
									if account_currency==self.company_currency
									else flt(amount, item.precision("net_amount"))),
								"cost_center": item.cost_center,
								"project": item.project or self.project
							}, account_currency, item=item)
						)
