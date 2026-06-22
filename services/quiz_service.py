import random
import string


def generate_quiz_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
