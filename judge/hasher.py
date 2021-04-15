from collections import OrderedDict

from argon2 import PasswordHasher
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.translation import gettext_lazy as _


class SpecialECOOPasswordHasher(BasePasswordHasher):
    algorithm = "argon2id"
    ph = PasswordHasher()

    def salt(self):
        return ''

    def encode(self, password, salt):
        assert password
        return self.ph.hash(password)[1:]

    def verify(self, password, encoded):
        algorithm, _ = encoded.split('$', 1)
        assert algorithm == self.algorithm
        return self.ph.verify("$" + encoded, password)

    def safe_summary(self, encoded):
        algorithm, hash = encoded.split('$', 1)
        assert algorithm == self.algorithm
        return OrderedDict([
            (_('algorithm'), algorithm),
            (_('hash'), mask_hash(hash)),
            ])
