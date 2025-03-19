from django.db import models


class Schedule(models.Model):
    # Номер генерируемого id, первичного ключа - идентификатор расписания

    # Номер страхового полиса (состоит из 16 цифр)
    animalId = models.CharField(max_length=16)

    # Название препарата
    medicamentName = models.CharField(max_length=30)

    # Дата и время последнего отправленного напоминания (UTC)
    lastSentNotification = models.DateTimeField()

    # Дата и время, после которых уведомления прекращаются, а запись о расписании удаляется (UTC)
    lastPlannedNotificationLimit = models.DateTimeField(null=True)

    # Интервал между приемами в часах ("от одного раза в день до ежечасного приёма")
    receptionInterval = models.PositiveSmallIntegerField()
