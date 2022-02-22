# Copyright (c) 2022, Marcos Tolentino and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import flt
from erpnext.accounts.utils import get_account_currency
from erpnext.controllers.accounts_controller import AccountsController

class TaxAssessment(AccountsController):
	pass

	def validate_qty_is_not_zero(self):
		#this needs item, wich we don't have
		pass

	def set_incoming_rate(self):
		#this needs item, wich we don't have
		pass

	def on_submit(self):
		if self.journal_entry:
			journal_entry = frappe.get_doc("Journal Entry", self.journal_entry) 
			
		if not journal_entry:
			frappe.throw("No Journal Entry found!")

		try:
			journal_entry.submit()
		except Exception as e:
			if type(e) in (str, list, tuple):
				frappe.msgprint(e)
			raise


	@frappe.whitelist()
	def calculate(self):
		accounting_period = frappe.get_doc("Accounting Period", self.accounting_period)
		si_list = frappe.db.sql(""" select * from `tabSales Invoice` 
			where (not accrued_income_date &&  posting_date between '{0}' and '{1}') 
			   or (accrued_income_date &&  accrued_income_date between '{0}' and '{1}')"""
			   .format(accounting_period.start_date, accounting_period.end_date),as_dict=1)
		if len(si_list) > 0:
			journal_entry = frappe.get_doc("Journal Entry", self.journal_entry) if self.journal_entry else frappe.new_doc("Journal Entry")
			journal_entry.voucher_type = "Journal Entry"
			journal_entry.user_remark = ("Tax Journal Entry for Tax Assessment {0}")\
				.format(self.name)
			journal_entry.company = self.company
			journal_entry.posting_date = accounting_period.end_date
			
			accounts = []
			total_tax_amount = 0

			for si in si_list:
				#todo
				tax_base_amount = si.total
				tax_amount = flt(tax_base_amount * 0.1633, 2)
				total_tax_amount += tax_amount

				accounts.append(
					self.get_gl_dict({
						"account": self.tax_expense_account,
						"against": self.tax_payable_account,
						"debit": tax_amount,
						"debit_in_account_currency": tax_amount,
						"cost_center": si.cost_center,
						"project": si.project
					})
				)

			accounts.append(
				self.get_gl_dict({
					"account": self.tax_payable_account,
					"credit": total_tax_amount,
					"credit_in_account_currency": total_tax_amount,
					"cost_center": si.cost_center,
					"project": si.project
				})
			)

			journal_entry.set("accounts", accounts)
			journal_entry.save()
			frappe.db.set_value("Tax Assessment", self.name, "journal_entry", journal_entry.name)




