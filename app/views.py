from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from app.models import Schedule


def schedule(request):
    if len(request.GET) == 0 and len(request.POST) > 0:
        errorText = ""
        post = request.POST
        medicament = post.get("medicament")
        Id = post.get("id")

        if medicament is None or medicament == "" or post.get("interval") is None or post.get(
                "interval") == "" or Id is None or Id == "":
            return render(request, post, context={"error": "Заполнены не все поля"})

        if not post.get("interval").isdigit():
            return render(request, post, context={"error": "Интервал приема введен некорректно"})
        interval = int(post.get("interval"))

        if post.get("duration") == "" or post.get("duration") is None:
            duration = 0
        elif not post.get("duration").isdigit():
            return render(request, post, context={"error": "Продолжительность приема введена некорректно"})
        else:
            duration = int(post.get("duration"))

        if len(medicament) > 30:
            errorText += "Название лекарства должно быть короче 30 символов. "

        if interval > 24 or interval < 1:
            errorText += "Интервал приема лекарства должен быть от 1 до 24-х часов. "

        if duration == 0 and post.get("duration") != "" and not post.get("duration") is None:
            errorText += "Продолжительность приёма должна быть или больше 1. "

        if len(Id) != 16 or not Id.isdigit():
            errorText += "Номер полиса состоит из 16 цифр. "

        if len(errorText) > 0:
            return render(request, post, context={"error": errorText})

        # TODO решить проблему округления минут

        newSchedule = Schedule.objects.create(animalId=Id,
                                              medicamentName=medicament,
                                              lastSentNotification=timezone.now(),
                                              lastPlannedNotificationLimit=(timezone.now() + timezone.timedelta(
                                                  days=duration)) if duration > 0 else None,
                                              receptionInterval=interval
                                              )
        # В ответ роут должен возвращать идентификатор (id) созданного
        # расписания из базы данных
        return HttpResponse(newSchedule.id)

    elif len(request.GET) == 0 and len(request.POST) == 0:
        return render(request, 'post.html')
    elif len(request.GET) == 2 and len(request.POST) == 0:
        # Какие-то действия с БД.

        # Возвращает данные о выбранном расписании с рассчитанным
        # графиком приёмов на день
        scheduleId = "123"
        return HttpResponse(scheduleId)
    else:
        return HttpResponse('Некорректные данные')
