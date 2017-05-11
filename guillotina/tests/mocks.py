from guillotina.db.interfaces import IStorage
from zope.interface import implementer


class MockDBTransaction:
    '''
    a db transaction is different than a transaction from guillotina
    '''

    def __init__(self, storage, trns):
        self._storage = storage
        self._transacion = trns


@implementer(IStorage)
class MockStorage:

    _cache = {}
    _read_only = False
    _transaction_strategy = 'merge'
    _cache_strategy = 'dummy'
    _options = {}

    def __init__(self, transaction_strategy='merge', cache_strategy='dummy'):
        self._transaction_strategy = transaction_strategy
        self._cache_strategy = cache_strategy
        self._transaction = None

    async def get_annotation(self, trns, oid, id):
        return None

    async def start_transaction(self, trns):
        self._transaction = MockDBTransaction(self, trns)
        return self._transaction

    async def get_next_tid(self, trns):
        return 1


class MockTransactionManager:
    _storage = None

    def __init__(self, storage=None):
        if storage is None:
            storage = MockStorage()
        self._storage = storage
