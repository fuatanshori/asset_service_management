from django.db import models
from django.utils import timezone

from equipment.models import Equipment


class MaintenanceSchedule(models.Model):
    """A planned maintenance event for a piece of equipment.

    Every MaintenanceSchedule owns exactly one MaintenanceLog (created
    automatically on first save — see save() below). The log is not
    required to be filled in immediately; it can be completed later via
    the log_edit view.

    Two invariants are enforced automatically in save():
      1. scheduled_date and log.date are kept in sync in both directions
         (editing either one updates the other).
      2. Changing maintenance_type re-triggers MaintenanceLog.save(),
         because equipment status logic can depend on schedule type in
         some deployments. Without this, switching a schedule's type
         without also touching the date would silently fail to
         re-evaluate the equipment's status.
    """

    TYPE_ROUTINE = "routine"
    TYPE_REPAIR = "repair"
    TYPE_CHOICES = [
        (TYPE_ROUTINE, "Perawatan Rutin"),
        (TYPE_REPAIR, "Perbaikan"),
    ]

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name="maintenance_schedules"
    )
    scheduled_date = models.DateField("Tanggal Jadwal")
    maintenance_type = models.CharField(
        "Jenis Perawatan", max_length=20, choices=TYPE_CHOICES, default=TYPE_ROUTINE
    )
    notes = models.TextField("Catatan", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date"]
        verbose_name = "Maintenance Schedule"
        verbose_name_plural = "Maintenance Schedules"

    def __str__(self):
        return f"{self.equipment.name} - {self.scheduled_date}"
    
    @property
    def is_editable(self):
        """Only the most recently created schedule for a given equipment
        can be edited — older schedules become immutable history once a
        newer one exists. Deletion is not affected by this; any schedule
        can still be deleted regardless of age."""
        latest_pk = (
            MaintenanceSchedule.objects.filter(equipment_id=self.equipment_id)
            .order_by("-created_at", "-pk")
            .values_list("pk", flat=True)
            .first()
        )
        return latest_pk == self.pk
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_scheduled_date = None
        old_maintenance_type = None
        if not is_new:
            old = type(self).objects.filter(pk=self.pk).values("scheduled_date", "maintenance_type").first()
            if old:
                old_scheduled_date = old["scheduled_date"]
                old_maintenance_type = old["maintenance_type"]

        super().save(*args, **kwargs)

        if is_new:
            MaintenanceLog.objects.create(schedule=self, date=self.scheduled_date)
        else:
            try:
                log = self.log
            except MaintenanceLog.DoesNotExist:
                log = None
            if log:
                date_changed = old_scheduled_date is not None and old_scheduled_date != self.scheduled_date
                type_changed = old_maintenance_type is not None and old_maintenance_type != self.maintenance_type

                if date_changed:
                    log.date = self.scheduled_date
                if date_changed or type_changed:
                    log.save()


class MaintenanceLog(models.Model):
    """The 1:1 actual maintenance record for a schedule, edited in place
    as work progresses (not a new row per update).

    `result` is the single source of truth for the linked Equipment's
    status:

        pending      -> Equipment.STATUS_SCHEDULED
        in_progress  -> Equipment.STATUS_UNDER_REPAIR
        completed    -> Equipment.STATUS_ACTIVE
        failed       -> Equipment.STATUS_DAMAGED

    `completed_date` is managed automatically:
      - First transition into completed/failed -> auto-filled with
        today's date (unless already set manually beforehand).
      - Reverted out of completed/failed back to another result ->
        cleared back to None.
      - Any other save (result unchanged) leaves completed_date alone.

    On every save(), this also writes `date` back to the parent
    schedule's `scheduled_date` if they've diverged — the other half of
    the bidirectional sync described in MaintenanceSchedule.save().

    NOTE: this is the agreed final version of this method — result maps
    to equipment status unconditionally, regardless of maintenance_type.
    Do not reintroduce a maintenance_type branch here.
    """

    RESULT_PENDING = "pending"
    RESULT_IN_PROGRESS = "in_progress"
    RESULT_COMPLETED = "completed"
    RESULT_FAILED = "failed"
    RESULT_CHOICES = [
        (RESULT_PENDING, "Sedang Dijadwalkan"),
        (RESULT_IN_PROGRESS, "Sedang Dikerjakan"),
        (RESULT_COMPLETED, "Selesai Pengerjaan"),
        (RESULT_FAILED, "Gagal"),
    ]

    schedule = models.OneToOneField(
        MaintenanceSchedule, on_delete=models.CASCADE, related_name="log"
    )
    date = models.DateField("Tanggal Schedule")
    technician = models.CharField("Teknisi", max_length=100, blank=True)
    action_taken = models.TextField("Tindakan", blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default=RESULT_PENDING)
    cost = models.DecimalField("Biaya", max_digits=12, decimal_places=2, default=0)
    photo_before = models.ImageField("Foto Sebelum", upload_to="maintenance_photos/before/", blank=True, null=True)
    photo_after = models.ImageField("Foto Sesudah", upload_to="maintenance_photos/after/", blank=True, null=True)
    photo_receipt = models.ImageField("Foto Kwitansi", upload_to="maintenance_photos/receipts/", blank=True, null=True)
    completed_date = models.DateField("Tanggal Selesai", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Maintenance Log"
        verbose_name_plural = "Maintenance Logs"

    def __str__(self):
        return f"{self.schedule.equipment.name} - {self.date}"
    
    @property
    def is_editable(self):
        """A log inherits editability from its schedule — see
        MaintenanceSchedule.is_editable."""
        return self.schedule.is_editable
    
    @property
    def result_color(self):
        return {
            self.RESULT_PENDING: "brand",
            self.RESULT_IN_PROGRESS: "amber",
            self.RESULT_COMPLETED: "green",
            self.RESULT_FAILED: "red",
        }.get(self.result, "muted")

    def save(self, *args, **kwargs):
        completion_results = (self.RESULT_COMPLETED, self.RESULT_FAILED)

        old = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values("result").first()
        old_was_completion = bool(old) and old["result"] in completion_results
        new_is_completion = self.result in completion_results

        if new_is_completion and not old_was_completion:
            if not self.completed_date:
                self.completed_date = timezone.localdate()
        elif not new_is_completion and old_was_completion:
            self.completed_date = None

        super().save(*args, **kwargs)

        equipment = self.schedule.equipment

        if self.result == self.RESULT_PENDING:
            new_status = Equipment.STATUS_SCHEDULED
        elif self.result == self.RESULT_IN_PROGRESS:
            new_status = Equipment.STATUS_UNDER_REPAIR
        elif self.result == self.RESULT_COMPLETED:
            new_status = Equipment.STATUS_ACTIVE
        elif self.result == self.RESULT_FAILED:
            new_status = Equipment.STATUS_DAMAGED
        else:
            new_status = None

        if new_status and equipment.status != new_status:
            equipment.status = new_status
            equipment.save(update_fields=["status", "updated_at"])

        schedule = self.schedule
        if schedule.scheduled_date != self.date:
            schedule.scheduled_date = self.date
            schedule.save()


def sync_equipment_status_from_remaining_logs(equipment):
    """Recompute equipment.status after a schedule is deleted — necessary
    because equipment.status is a derived field that any of the
    equipment's multiple schedules could have last written. An "open"
    (not completed/failed) log always takes priority over resolved ones,
    since it represents work that's still ongoing. If nothing remains at
    all, the equipment is considered Active."""
    logs = MaintenanceLog.objects.filter(schedule__equipment=equipment)

    open_log = (
        logs.exclude(result__in=[MaintenanceLog.RESULT_COMPLETED, MaintenanceLog.RESULT_FAILED])
        .order_by("-updated_at")
        .first()
    )
    reference_log = open_log or logs.order_by("-updated_at").first()

    if reference_log is None:
        new_status = Equipment.STATUS_ACTIVE
    elif reference_log.result == MaintenanceLog.RESULT_PENDING:
        new_status = Equipment.STATUS_SCHEDULED
    elif reference_log.result == MaintenanceLog.RESULT_IN_PROGRESS:
        new_status = Equipment.STATUS_UNDER_REPAIR
    elif reference_log.result == MaintenanceLog.RESULT_COMPLETED:
        new_status = Equipment.STATUS_ACTIVE
    elif reference_log.result == MaintenanceLog.RESULT_FAILED:
        new_status = Equipment.STATUS_DAMAGED
    else:
        new_status = Equipment.STATUS_ACTIVE

    if equipment.status != new_status:
        equipment.status = new_status
        equipment.save(update_fields=["status", "updated_at"])