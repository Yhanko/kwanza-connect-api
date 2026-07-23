import os

files_to_check = [
    'audit/domain/entities.py',
    'audit/services/use_cases.py',
    'app/audit_service.py',
    'audit/__init__.py',
    'audit/tests/__init__.py',
    'audit/tests/unit/__init__.py',
]

for path in files_to_check:
    if os.path.exists(path):
        with open(path, 'rb') as f:
            content = f.read()
            if b'\x00' in content:
                print(f'{path} contains null bytes')
            else:
                print(f'{path} is clean')
    else:
        print(f'{path} not found')
