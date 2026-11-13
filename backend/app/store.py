from app.schemas import Preferences

class Store:
    """In-memory starter store. Replace with PostgreSQL before production."""
    def __init__(self):
        self.preferences = Preferences()
        self.boards = {}
        self.jobs = {}
