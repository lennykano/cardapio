from dbus.exceptions import DBusException

class CardapioPlugin(CardapioPluginInterface):

	"""
	Tomboy plugin based on it's D-Bus interface. Documentation:
	http://arstechnica.com/open-source/news/2007/09/using-the-tomboy-d-bus-interface.ars

	The plugin looks for notes with titles and contents similar to the search string.
	If it can't find any, it provides user with the handy 'create a note with this
	title' link.

	Please note that the plugin only works when Tomboy is on. You don't need to
	turn it on before starting Cardapio or before initializing the plugin. You
	just need to turn it on before performing a Cardapio search.
	"""

	# Cardapio's variables
	author = 'Pawel Bara'
	name = _('Tomboy')
	description = _('Search for Tomboy notes')
	version = '0.9b'

	url = ''
	help_text = ''

	default_keyword = 'tomboy'

	plugin_api_version = 1.37

	search_delay_type = 'local search update delay'

	category_name = _('Tomboy Results')
	category_tooltip = _('Your Tomboy notes')

	category_icon = 'tomboy'
	fallback_icon = ''

	hide_from_sidebar = True

	def __init__(self, cardapio_proxy):
		cardapio_proxy.write_to_log(self, 'initializing Tomboy plugin')

		self.cardapio = cardapio_proxy

		# Tomboy's D-Bus constants
		self.dtomboy_bus_name = 'org.gnome.Tomboy'
		self.dtomboy_object_path = '/org/gnome/Tomboy/RemoteControl'
		self.dtomboy_iface_name = 'org.gnome.Tomboy.RemoteControl'

		# take the maximum number of results into account
		self.results_limit = self.cardapio.settings['search results limit']
		self.long_results_limit = self.cardapio.settings['long search results limit']

		try:
			self.bus = dbus.SessionBus()
			# we track Tomboy's on / off status
			self.bus.watch_name_owner(self.dtomboy_bus_name, self.on_dbus_name_change)

			self.loaded = True

		except DBusException as ex:
			self.cardapio.write_to_log(self, 'Tomboy plugin initialization error: {0}'.format(str(ex)), is_error = True)
			self.loaded = False

	def on_dbus_name_change(self, connection_name):
		"""
		This method effectively tracks down the events of Tomboy app starting
		and shutting down. When the app shuts down, this callback nullifies our
		Tomboy's proxy. When the app starts, the callback sets the valid proxy
		again.
		"""

		if len(connection_name) == 0:
			self.tomboy = None
		else:
			bus_object = self.bus.get_object(connection_name, self.dtomboy_object_path)
			self.tomboy = dbus.Interface(bus_object, self.dtomboy_iface_name)

	def search(self, text, long_search = False):
		if len(text) == 0:
			return

		# send empty results to Cardapio if Tomboy's off
		if self.tomboy is None:
			self.cardapio.handle_search_result(self, [], text)

		self.cardapio.write_to_log(self, 'searching for Tomboy notes with topic like {0}'.format(text), is_debug = True)

		current_results_limit = self.long_results_limit if long_search else self.results_limit

		# prepare a parametrized callback that remembers the current search text and
		# the result limit
		callback = DBusParametrizedCallback(self.tomboy, self.finalize_search,
			text, current_results_limit)

		# we ask for a case insensitive search
		self.tomboy.SearchNotes(text.lower(), False, reply_handler = callback.handle_search_result,
			error_handler = self.handle_search_error)

	def finalize_search(self, items, text):
		"""
		DBusParametrizedCallback invokes this when it finishes gathering
		single search results. This method finalizes the search, then
		passes the result to Cardapio.
		"""

		# if there are no results, we'll add the 'create a note with this
		# title' link
		if len(items) == 0:
			items.append({
				'name'         : _('Create this note'),
				'tooltip'      : _('Create a new note with this title in Tomboy'),
				'icon name'    : 'tomboy',
				'type'         : 'callback',
				'command'      : self.tomboy_create_note,
				'context menu' : None
			})

		# the 'search more' option is always present
		items.append({
			'name'         : _('Show additional notes'),
			'tooltip'      : _('Show additional notes in Tomboy'),
			'icon name'    : 'tomboy',
			'type'         : 'callback',
			'command'      : self.tomboy_find_more,
			'context menu' : None
		})

		self.cardapio.handle_search_result(self, items, text)

	def handle_search_error(self, error):
		"""
		Error callback to asynchronous Tomboy's D-Bus call.
		"""

		self.cardapio.handle_search_error(self, 'Tomboy search error: {0}'.format(str(error)))

	def tomboy_create_note(self, text):
		"""
		Creates a new note with the given title, then displays it to
		the user.
		"""

		# try to avoid errors if Tomboy's off
		if self.tomboy is None:
			return

		new_note = self.tomboy.CreateNamedNote(text)
		self.tomboy.DisplayNote(new_note)

	def tomboy_find_more(self, text):
		"""
		Opens Tomboy's 'Search more' window.
		"""

		# try to avoid errors if Tomboy's off
		if self.tomboy is None:
			return

		self.tomboy.DisplaySearchWithText(text)

class DBusParametrizedCallback:
	"""
	This class resolves a problem with D-Bus, namely it's callbacks,
	which don't take some kind of a user data argument.

	DBusParametrizedCallback serves as a parametrized wrapper over
	the asynchronous callback.
	"""

	def __init__(self, tomboy, result_callback, text, result_limit):
		self.tomboy = tomboy
		self.result_callback = result_callback

		self.text = text
		self.result_limit = result_limit

	def handle_search_result(self, result):
		"""
		Callback to asynchronous Tomboy's D-Bus call. It gathers
		results and then passes those back to the main plugin class
		through the result_callback method.
		"""

		# pass empty results to main class if Tomboy's off
		if self.tomboy is None:
			self.result_callback([], self.text)

		items = []

		# if we have any results...
		i = 0
		for note in result:

			# exit after gathering enough results
			if i == self.result_limit:
				break
			i += 1

			# add 'open this note' item
			items.append({
				'name'         : self.tomboy.GetNoteTitle(note),
				'tooltip'      : _('Open this note'),
				'icon name'    : 'tomboy',
				'type'         : 'xdg',
				'command'      : note,
				'context menu' : None
			})

		# pass all of the gathered items and the current search
		# text to the main plugin class
		self.result_callback(items, self.text)
