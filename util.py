# From http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)
