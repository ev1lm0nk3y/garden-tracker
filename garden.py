import webapp2

import garden_common
import garden_handlers

app_config = {
    'webapp2_extras.sessions': {
        'cookie_name': '_simpleauth_sess',
        'secret_key': garden_common.SESSION_KEY
    },
    'webapp2_extras.auth': {
        'user_attributes': []
    }
}

routes = [
    webapp2.Route('/admin', handler='garden_handlers.AdminConsole',
                  name='admin-console', handler_method='AdminHome'),
    webapp2.Route('/admin/plants', handler='garden_handlers.AdminConsole',
                  name='show-plants', handler_method='ShowPlants'),
    webapp2.Route('/admin/upload_plants', handler='garden_handlers.AdminConsole',
                  name='add-plants', handler_method='AddPlants'),
    webapp2.Route('/login', handler='garden_handlers.Authenticate',
                  name='login', handler_method='SignIn'),
    webapp2.Route('/logout', handler='garden_handlers.Authenticate',
                  name='logout', handler_method='LogOut'),
    webapp2.Route('/mygarden', handler='garden_handlers.User',
                  name='view-profile', handler_method='Main'),
    webapp2.Route('/mygarden/create_garden', handler='garden_handlers.User',
                  name='create-garden', handler_method='CreateGardenForm',
                  methods=['GET']),
    webapp2.Route('/mygarden/create_garden', handler='garden_handlers.User',
                  name='create-garden', handler_method='CreateGardenAction',
                  methods=['POST']),
    webapp2.Route('/mygarden/delete', handler='garden_handlers.User',
                  name='delete-garden', handler_method='DeleteGarden'),
    webapp2.Route('/mygarden/updateprofile', handler='garden_handlers.User',
                  name='edit-profile', handler_method='UpdateProfile'),
    webapp2.Route('/', handler='garden_handlers.Main', name='main-page'),

    # This next line should always be the last one
    (garden_common.DECORATOR.callback_path,
     garden_common.DECORATOR.callback_handler()),
]


app = webapp2.WSGIApplication(
    routes,
    config=app_config,
    debug=True)
