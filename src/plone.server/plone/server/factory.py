# -*- coding: utf-8 -*-
import asyncio

import sys

import ZODB

from aiohttp import web

from concurrent.futures import ThreadPoolExecutor

from pkg_resources import iter_entry_points

from plone.registry import Registry
from plone.registry.interfaces import IRegistry
from plone.server.content import Site
from plone.server.registry import ILayers
from plone.server.registry import (IAuthExtractionPlugins,
                                        IAuthPloneUserPlugins)
from plone.server.auth.oauth import (IPloneJWTExtractionConfig,
                                              IPloneOAuthConfig)
from plone.server.request import RequestAwareDB, RequestAwareTransactionManager
from plone.server.traversal import TraversalRouter

import transaction

from zope.configuration.config import ConfigurationMachine
from zope.configuration.xmlconfig import include, registerCommonDirectives
from zope.component import getAllUtilitiesRegisteredFor
from plone.server.async import IAsyncUtility
import functools



def make_app():
    # Initialize aiohttp app
    app = web.Application(router=TraversalRouter())

    # Initialize asyncio executor worker
    app.executor = ThreadPoolExecutor(max_workers=1)

    # Initialize global (threadlocal) ZCA configuration
    app.config = ConfigurationMachine()
    registerCommonDirectives(app.config)
    include(app.config, 'configure.zcml', sys.modules['plone.server'])
    for ep in iter_entry_points('plone.server'):  # auto-include applications
        include(app.config, 'configure.zcml', ep.load())
    app.config.execute_actions()

    # Initialize DB
    db = ZODB.DB('Data.fs')
    conn = db.open()
    if getattr(conn.root, 'data', None) is None:
        with transaction.manager:
            dbroot = conn.root()

            # Creating a testing site
            dbroot['plone'] = Site('plone')
            plonesite = dbroot['plone']

            # Creating and registering a local registry
            plonesite['registry'] = Registry()
            plonesite['registry'].registerInterface(ILayers)
            plonesite['registry'].registerInterface(IAuthPloneUserPlugins)
            plonesite['registry'].registerInterface(IAuthExtractionPlugins)

            plonesite['registry'].forInterface(ILayers).active_layers = \
                ["plone.server.api.layer.IDefaultLayer"]

            plonesite['registry'].forInterface(IAuthExtractionPlugins).active_plugins = \
                ["plone.server.auth.oauth.PloneJWTExtraction"]

            plonesite['registry'].forInterface(IAuthPloneUserPlugins).active_plugins = \
                ["plone.server.auth.oauth.OAuthPloneUserFactory"]

            # Set default plugins
            plonesite['registry'].registerInterface(IPloneJWTExtractionConfig)
            plonesite['registry'].registerInterface(IPloneOAuthConfig)

            sm = plonesite.getSiteManager()

            from plone.dexterity import utils
            obj = utils.createContent('Todo')
            obj.id = 'obj1'
            plonesite['obj1'] = obj
            obj.__parent__ = plonesite
            sm.registerUtility(plonesite['registry'], provided=IRegistry)

    conn.close()
    db.close()

    loop = asyncio.get_event_loop()
    for utility in getAllUtilitiesRegisteredFor(IAsyncUtility):
        loop.call_soon(asyncio.ensure_future(utility.initialize(app=app)))

    # Set request aware database for app
    db = RequestAwareDB('Data.fs')
    tm_ = RequestAwareTransactionManager()
    # While _p_jar is a funny name, it's consistent with Persistent API
    app._p_jar = db.open(transaction_manager=tm_)

    # Set router root from the ZODB connection
    app.router.set_root_factory(app._p_jar.root)

    return app