from argon2 import PasswordHasher
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.datastructures import SortedDict

class SpecialECOOPasswordHasher(BasePasswordHasher):
    algorithm = "argon2id"
    ph = PasswordHasher()

    def salt(self):
        return ''

    def encode(self, password, salt):
        assert password
        return self.ph.hash(password)

    def verify(self, password, encoded):
        algorithm, _ = encoded[1:].split('$', 1)
        assert algorithm == self.algorithm
        return self.ph.verify(encoded, password)

    def safe_summary(self, encoded):
        algorithm, hash = encoded[1:].split('$', 1)
        assert algorithm == self.algorithm
        return SortedDict([
            (_('algorithm'), algorithm),
            (_('hash'), mask_hash(hash)),
            ])
