import secrets, string

def path_image_or_file(instance,filename):
    model_name = instance.__class__.__name__.lower()
    return f'uploads/{model_name}/{instance.pk or "new"}/{filename}'
    

def _code(len:int):
    hash_code = string.digits
    return "".join(secrets.choice(hash_code) for _ in range(len))

