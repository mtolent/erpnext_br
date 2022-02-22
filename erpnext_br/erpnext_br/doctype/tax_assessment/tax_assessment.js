// Copyright (c) 2022, Marcos Tolentino and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tax Assessment', {
	refresh: function(frm) {
		frm.add_custom_button(__('Payment'), () => {
			console.log('call frappe');
			frappe.call({
				"method": "calculate",
				"doc": frm.doc,
				callback: function(r) {
					console.log(r);
				}
			});
		},  __('Create'));
	}
});
