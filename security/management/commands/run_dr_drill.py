"""
Comando de Gestão para Simulação de Recuperação de Desastres (DRP Drill / RTO BNA).
"""

from django.core.management.base import BaseCommand
from security.services.backup_service import BackupService


class Command(BaseCommand):
    help = 'Executa simulado automatizado de recuperacao de desastres (DRP Drill) medindo o RTO'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("[BCP/DRP] INICIANDO DISASTER RECOVERY DRILL (SANDBOX BNA)"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        try:
            success, rto_seconds, notes = BackupService.run_disaster_recovery_drill()
            if success:
                self.stdout.write(self.style.SUCCESS(f"  [OK] RTO Medido: {rto_seconds}s (Meta BNA <= 1800s)"))
                self.stdout.write(self.style.SUCCESS(f"  [OK] Detalhes: {notes}"))
                self.stdout.write("\n" + self.style.SUCCESS("[SUCESSO] Simulado DRP aprovado com sucesso!"))
            else:
                self.stdout.write(self.style.ERROR(f"  [FALHA] Simulado reprovado: {notes}"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha na execucao do simulado DRP: {exc}"))
            raise exc
