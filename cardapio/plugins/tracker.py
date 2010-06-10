import urllib2, os

if '_' not in locals():
	_ = lambda x: x

class CardapioPlugin(CardapioPluginInterface):

	author             = 'Thiago Teixeira'
	name               = 'Tracker plugin'
	description        = 'Search local files and folders indexed with Tracker'
	version            = '1.0'

	plugin_api_version = 1.0

	search_delay_type  = 'local search update delay'

	category_name      = _('Local Results')
	category_icon      = 'system-search'
	hide_from_sidebar  = True


	def __init__(self, settings, handle_search_result, handle_search_error):

		self.tracker = None
		bus = dbus.SessionBus()

		if bus.request_name('org.freedesktop.Tracker1') == dbus.bus.REQUEST_NAME_REPLY_IN_QUEUE:
			tracker_object = bus.get_object('org.freedesktop.Tracker1', '/org/freedesktop/Tracker1/Resources')
			self.tracker = dbus.Interface(tracker_object, 'org.freedesktop.Tracker1.Resources') 

		self.search_results_limit = settings['search results limit']

		self.cardapio_results_handler = handle_search_result
		self.cardapio_error_handler = handle_search_error


	def search(self, text):

		# no .lower(), since there's no fn:lower-case in tracker (yet!)
		#text = urllib2.quote(text).lower()
		text = urllib2.quote(text)

		self.tracker.SparqlQuery(
			"""
				SELECT ?uri ?mime
				WHERE { 
					?item a nie:InformationElement;
						nie:url ?uri;
						nie:mimeType ?mime;
						tracker:available true.
					FILTER (fn:contains(?uri, "%s"))
					}
				ORDER BY ASC(?uri)
				LIMIT %d
			""" 
			% (text, self.search_results_limit),
			dbus_interface='org.freedesktop.Tracker1.Resources',
			reply_handler=self.prepare_and_handle_search_result,
			error_handler=self.handle_search_error
			)


	def handle_search_error(self, error):

		self.cardapio_error_handler(self, error)


	def prepare_and_handle_search_result(self, results):

		formatted_results = []	

		for result in results:
			
			dummy, canonical_path = urllib2.splittype(result[0])
			parent_name, child_name = os.path.split(canonical_path)
			icon_name = result[1]

			formatted_result = {}
			formatted_result['name'] = child_name
			formatted_result['icon name'] = icon_name
			formatted_result['tooltip'] = canonical_path
			formatted_result['xdg uri'] = canonical_path

			formatted_results.append(formatted_result)

		self.cardapio_results_handler(self, formatted_results)
