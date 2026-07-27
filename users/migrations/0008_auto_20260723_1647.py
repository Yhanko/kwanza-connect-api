import unicodedata
import random
import re
from django.db import migrations


def generate_usernames(apps, schema_editor):
    User = apps.get_model('users', 'User')
    IdentityDocument = apps.get_model('users', 'IdentityDocument')

    for user in User.objects.filter(username__isnull=True):
        base = 'user'
        if user.full_name:
            parts = user.full_name.split()
            if len(parts) > 1:
                base = f"{parts[0].lower()}{parts[-1].lower()}"
            else:
                base = parts[0].lower()
                
        base = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
        base = re.sub(r'[^a-z0-9]', '', base)
        if not base:
            base = 'user'
            
        suffix = ""
        # Tentar obter doc_number da BD
        doc = IdentityDocument.objects.filter(user_id=user.id).first()
        if doc and doc.doc_number:
            nums = re.findall(r'\d+', doc.doc_number)
            if nums:
                suffix = "".join(nums)[-3:]
                
        if not suffix:
            suffix = str(random.randint(100, 999))
            
        username = f"{base}{suffix}"
        
        # Validar unicidade para o batch
        original = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{original}{counter}"
            counter += 1
            
        user.username = username
        user.save(update_fields=['username'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_user_username'),
    ]

    operations = [
        migrations.RunPython(generate_usernames, reverse_code=migrations.RunPython.noop),
    ]

