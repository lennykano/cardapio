import_error = None

try:
	import xapian
	import sys
	import apt
	import os

except Exception, exception:
	import_error = exception

class CardapioPlugin(CardapioPluginInterface):

	author             = 'Clifton Mulkey'
	name               = _('Software Center')
	description        = _('Search for new applications in the Software Center')

	url                = ''
	help_text          = ''
	version            = '1.1'

	plugin_api_version = 1.3

	search_delay_type  = 'local search update delay'
	category_name      = _('Available Software')
	category_icon      = 'softwarecenter'
	category_tooltip   = _('Software available to install on your system')

	fallback_icon      = 'applications-other'

	hide_from_sidebar = True 		


	def __init__(self, cardapio_proxy):
		'''	
		This method is called when the plugin is enabled.
		Nothing much to be done here except initialize variables and set loaded to True
		'''
		
		self.c = cardapio_proxy
	   	self.loaded = False

		self.num_search_results = self.c.settings['search results limit']
		
		if import_error:
			self.c.write_to_log(self, 'Could not import certain modules', is_error = True)
			self.c.write_to_log(self, import_error, is_error = True)
			return

		software_center_path = '/usr/share/software-center'

		if not os.path.exists(software_center_path):
			self.c.write_to_log(self, 'Could not find the software center path', is_error = True)
			return

		sys.path.append(software_center_path)

		try:
			from softwarecenter.enums import XAPIAN_VALUE_POPCON
			from softwarecenter.db.database import StoreDatabase
			from softwarecenter.view.appview import AppViewFilter

		except Exception, exception:
			self.c.write_to_log(self, 'Could not load the software center modules', is_error = True)
			self.c.write_to_log(self, exception, is_error = True)
			return

		cache = apt.Cache() # this line is really slow! around 0.28s on my computer!
		db_path = '/var/cache/software-center/xapian'

		if not os.path.exists(db_path):
			self.c.write_to_log(self, 'Could not find the database path', is_error = True)
			return

		self.db = StoreDatabase(db_path, cache)
		self.db.open()
		self.apps_filter = AppViewFilter(self.db, cache)
		self.apps_filter.set_not_installed_only(True)
		self.apps_filter.set_only_packages_without_applications(True)

		self.XAPIAN_VALUE_ICON = 172
		self.XAPIAN_VALUE_POPCON = 176
		self.XAPIAN_VALUE_SUMMARY = 177

		self.action = {
			'name'         : _('Open Software Center'),
			'tooltip'      : _('Search for more software in the Software Center'),
			'icon name'    : 'system-search', # using this icon because otherwise it looks strange...
			'type'         : 'raw',
			'command'      : 'software-center',
			'context menu' : None,
			}

		self.context_menu_action_name = _('_Install %s')
		self.context_menu_action_tooltip = _('Install this package without opening the Software Center')

		self.default_tooltip_str = _('Show %s in the Software Center')
		self.summary_str = _('Description:')
		
	   	self.loaded = True # set to true if everything goes well
		

	def search(self, text):
  
		results = []
		
		query = self.db.get_query_list_from_search_entry(text)
		
		enquire = xapian.Enquire(self.db.xapiandb)
		enquire.set_query(query[1])
		enquire.set_sort_by_value_then_relevance(self.XAPIAN_VALUE_POPCON)
		matches = enquire.get_mset(0, len(self.db))

		i = 0
		for m in matches:
			if not i < self.num_search_results : break
			
			doc = m[xapian.MSET_DOCUMENT]
			pkgname = self.db.get_pkgname(doc)
			summary = doc.get_value(self.XAPIAN_VALUE_SUMMARY)

			name = doc.get_data()

			icon_name = 'applications-other'

			if self.apps_filter.filter(doc, pkgname) and summary:
				icon_name = os.path.splitext(doc.get_value(self.XAPIAN_VALUE_ICON))[0]

				if not icon_name:
					icon_name = 'applications-other'

				tooltip = self.default_tooltip_str % name 

				if summary:
					tooltip += '\n' + self.summary_str + ' ' + summary

				item = {
					'name'      : name,
					'tooltip'   : tooltip,
					'icon name' : icon_name,
					'type'      : 'raw',
					'command'   : "software-center '%s'" % pkgname,
					'context menu' : [
							{
								'name'      : self.context_menu_action_name % name,
								'tooltip'   : self.context_menu_action_tooltip,
								'icon name' : icon_name,
								'type'      : 'xdg',
								'command'   : "apt:%s" % pkgname,
							},
						]
					}

				results.append(item)
				i += 1

		if results:
			results.append(self.action)
	
		self.c.handle_search_result(self, results)

