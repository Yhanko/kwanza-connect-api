"""
Comando de Gestão para Backup Criptografado do Banco de Dados (Sandbox BNA / BCP).
"""

from django.core.management.base import BaseCommand
from security.services.backup_service import BackupService


class Command(BaseCommand):
    help = 'Executa backup encriptado com AES-256 e validação SHA-256 da base de dados'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("[BCP/DRP] INICIANDO BACKUP CRIPTOGRAFADO (SANDBOX BNA)"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        try:
            backup_log = BackupService.create_database_backup()
            self.stdout.write(self.style.SUCCESS(f"  [OK] Ficheiro gerado: {backup_log.filename}"))
            self.stdout.write(self.style.SUCCESS(f"  [OK] Tamanho: {backup_log.file_size_bytes} bytes"))
            self.stdout.write(self.style.SUCCESS(f"  [OK] Checksum SHA-256: {backup_log.sha256_checksum}"))
            self.stdout.write(self.style.SUCCESS(f"  [OK] Tempo de execucao: {backup_log.duration_seconds}s"))
            self.stdout.write(self.style.SUCCESS(f"  [OK] Criptografia: {backup_log.encrypted_with}"))
            self.stdout.write("\n" + self.style.SUCCESS("[SUCESSO] Backup concluido e validado em conformidade com o RPO <= 15m."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha ao gerar backup: {exc}"))
            raise exc
