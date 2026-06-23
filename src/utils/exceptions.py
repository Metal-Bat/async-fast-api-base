class NotFoundException(Exception):
    pass


class NotAllowedException(Exception):
    pass


class InvalidCredentialError(Exception):
    pass


class UserNotFoundException(NotFoundException):
    pass


class InactiveUserException(Exception):
    pass
