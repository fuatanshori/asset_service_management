from django.db import models
from django.utils import timezone

from equipment.models import Equipment


def get_latest_schedule_for_equipment(equipment):
    """The schedule that currently "owns" the equipment's status — always
    the most recently CREATED one (by created_at), regardless of which
    schedule/log was most recently edited."""
    return (
        MaintenanceSchedule.objects.filter(equipment=equipment)
        .order_by("-created_at", "-pk")
        .first()
    )


def sync_equipment_status(equipment):
    """Recompute equipment.status purely from the equipment's LATEST
    SCHEDULE's log result — never from whichever log was most recently
    edited/updated. This means editing an older schedule's log (any
    field, including result) can never corrupt the equipment's current
    status; only the newest schedule for that equipment is ever
    consulted. Called both after any log save and after a schedule
    delete."""
    latest_schedule = get_latest_schedule_for_equipment(equipment)

    if latest_schedule is None:
        new_status = Equipment.STATUS_ACTIVE
    else:
        try:
            log = latest_schedule.log
        except MaintenanceLog.DoesNotExist:
            log = None

        if log is None:
            new_status = Equipment.STATUS_ACTIVE
        elif log.result == MaintenanceLog.RESULT_PENDING:
            new_status = Equipment.STATUS_SCHEDULED
        elif log.result == MaintenanceLog.RESULT_IN_PROGRESS:
            new_status = Equipment.STATUS_UNDER_REPAIR
        elif log.result == MaintenanceLog.RESULT_COMPLETED:
            new_status = Equipment.STATUS_ACTIVE
        elif log.result == MaintenanceLog.RESULT_FAILED:
            new_status = Equipment.STATUS_DAMAGED
        else:
            new_status = Equipment.STATUS_ACTIVE

    if equipment.status != new_status:
        equipment.status = new_status
        equipment.save(update_fields=["status", "updated_at"])


class MaintenanceSchedule(models.Model):
    """A planned maintenance event for a piece of equipment.

    Every MaintenanceSchedule owns exactly one MaintenanceLog (created
    automatically on first save — see save() below). The log is not
    required to be filled in immediately; it can be completed later via
    the log_edit view.

    Two invariants are enforced automatically in save():
      1. scheduled_date and log.date are kept in sync in both directions
         (editing either one updates the other).
      2. Changing maintenance_type re-triggers MaintenanceLog.save(), so
         status logic downstream always sees a consistent state.

    is_editable only gates the `result` field in MaintenanceLogForm — it
    does NOT block access to editing anything else. See
    MaintenanceLog.is_editable for details.
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
        """Whether this is the most recently created schedule for its
        equipment. Only used to disable the `result` field in
        MaintenanceLogForm — purely to avoid confusing/misleading
        historical records. Does not gate access to editing anything
        else; equipment.status is protected independently by
        sync_equipment_status(), which always references the latest
        schedule regardless of what gets edited."""
        latest = get_latest_schedule_for_equipment(self.equipment)
        return latest is not None and latest.pk == self.pk

    def save(self, *args, skip_log_sync=False, **kwargs):
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
        elif not skip_log_sync:
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
                    # skip_schedule_sync=True: log ini sudah pasti sinkron
                    # dengan schedule (baru saja disamakan di atas), jadi
                    # tidak perlu log.save() memicu schedule.save() lagi.
                    log.save(skip_schedule_sync=True)


class MaintenanceLog(models.Model):
    """The 1:1 actual maintenance record for a schedule, edited in place
    as work progresses (not a new row per update).

    `completed_date` is managed automatically:
      - First transition into completed/failed -> auto-filled with
        today's date (unless already set manually beforehand).
      - Reverted out of completed/failed back to another result ->
        cleared back to None.
      - Any other save (result unchanged) leaves completed_date alone.

    On every save(), equipment.status is recomputed via
    sync_equipment_status() — which always reads from the equipment's
    LATEST schedule, not necessarily this one. This makes it safe to
    edit an older log's fields without accidentally corrupting the
    equipment's current status.

    date and the parent schedule's scheduled_date are kept in sync in
    both directions.
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
    def result_color(self):
        return {
            self.RESULT_PENDING: "brand",
            self.RESULT_IN_PROGRESS: "amber",
            self.RESULT_COMPLETED: "green",
            self.RESULT_FAILED: "red",
        }.get(self.result, "muted")

    @property
    def is_editable(self):
        """See MaintenanceSchedule.is_editable — inherited from the
        parent schedule."""
        return self.schedule.is_editable

    def save(self, *args, skip_schedule_sync=False, **kwargs):
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

        # Status barang selalu dihitung dari jadwal TERBARU milik barang
        # ini — bukan dari log yang baru saja disimpan.
        sync_equipment_status(self.schedule.equipment)

        if not skip_schedule_sync:
            schedule = self.schedule
            if schedule.scheduled_date != self.date:
                schedule.scheduled_date = self.date
                # skip_log_sync=True: schedule ini sudah pasti sinkron
                # dengan log (baru saja disamakan di atas), jadi tidak
                # perlu schedule.save() memicu log.save() lagi.
                schedule.save(skip_log_sync=True)