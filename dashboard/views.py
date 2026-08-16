#dashboard/views.py

from django.core.paginator import Paginator
from django.shortcuts import render
import json
from equipment.analytics import get_equipment_status_breakdown
from equipment.models import Equipment
from maintenance.analytics import (
    get_cost_by_month,
    get_cost_summary,
    get_maintenance_type_breakdown,
    get_overdue_schedules,
    get_result_breakdown,
    get_service_ranking_queryset,
    get_technician_ranking_queryset,
    get_top_serviced_equipment,
    get_top_technicians,
)
from maintenance.models import MaintenanceLog, MaintenanceSchedule
from .forms import WidgetDateFilterForm, WidgetRankingFilterForm


def _preserve_params(get_params, exclude_prefix):
    prefix = exclude_prefix + "-"
    return [(k, v) for k, v in get_params.items() if not k.startswith(prefix)]


def dashboard(request):
    cost_filter = WidgetDateFilterForm(request.GET, prefix="cost")
    type_filter = WidgetDateFilterForm(request.GET, prefix="type")
    result_filter = WidgetDateFilterForm(request.GET, prefix="result")
    topeq_filter = WidgetRankingFilterForm(request.GET, prefix="topeq")
    toptech_filter = WidgetRankingFilterForm(request.GET, prefix="toptech")
    for f in (cost_filter, type_filter, result_filter, topeq_filter, toptech_filter):
        f.is_valid()

    cost_by_month = get_cost_by_month(
        date_from=cost_filter.cleaned_data.get("date_from"),
        date_to=cost_filter.cleaned_data.get("date_to"),
    )
    type_breakdown = get_maintenance_type_breakdown(
        date_from=type_filter.cleaned_data.get("date_from"),
        date_to=type_filter.cleaned_data.get("date_to"),
    )
    result_breakdown = get_result_breakdown(
        date_from=result_filter.cleaned_data.get("date_from"),
        date_to=result_filter.cleaned_data.get("date_to"),
    )
    topeq_limit = int(topeq_filter.cleaned_data.get("limit") or 5)
    top_serviced_equipment = get_top_serviced_equipment(
        date_from=topeq_filter.cleaned_data.get("date_from"),
        date_to=topeq_filter.cleaned_data.get("date_to"),
        limit=topeq_limit,
    )
    toptech_limit = int(toptech_filter.cleaned_data.get("limit") or 5)
    top_technicians = get_top_technicians(
        date_from=toptech_filter.cleaned_data.get("date_from"),
        date_to=toptech_filter.cleaned_data.get("date_to"),
        limit=toptech_limit,
    )

    status_breakdown = get_equipment_status_breakdown()
    overdue_schedules, overdue_count = get_overdue_schedules()

    context = {
        "active_page": "dashboard",
        "total_equipment": Equipment.objects.count(),
        "equipment_active": status_breakdown["active"],
        "equipment_scheduled": status_breakdown["scheduled"],
        "equipment_under_repair": status_breakdown["under_repair"],
        "equipment_damaged": status_breakdown["damaged"],
        "cost_summary": get_cost_summary(),
        "upcoming_schedules": (
            MaintenanceSchedule.objects.select_related("equipment", "log")
            .filter(log__result__in=[MaintenanceLog.RESULT_PENDING, MaintenanceLog.RESULT_IN_PROGRESS])
            .order_by("scheduled_date")[:8]
        ),
        "overdue_schedules": overdue_schedules,
        "overdue_count": overdue_count,

        "cost_filter": cost_filter,
        "type_filter": type_filter,
        "result_filter": result_filter,
        "topeq_filter": topeq_filter,
        "toptech_filter": toptech_filter,

        "cost_preserve_params": _preserve_params(request.GET, "cost"),
        "type_preserve_params": _preserve_params(request.GET, "type"),
        "result_preserve_params": _preserve_params(request.GET, "result"),
        "topeq_preserve_params": _preserve_params(request.GET, "topeq"),
        "toptech_preserve_params": _preserve_params(request.GET, "toptech"),

        "chart_labels_json": json.dumps(cost_by_month["labels"]),
        "chart_values_json": json.dumps(cost_by_month["values"]),
        "status_chart_json": json.dumps([
            status_breakdown["active"], status_breakdown["scheduled"],
            status_breakdown["under_repair"], status_breakdown["damaged"],
        ]),
        "type_labels_json": json.dumps([r["label"] for r in type_breakdown]),
        "type_values_json": json.dumps([r["total"] for r in type_breakdown]),
        "result_labels_json": json.dumps([r["label"] for r in result_breakdown]),
        "result_values_json": json.dumps([r["total"] for r in result_breakdown]),

        "top_serviced_equipment": top_serviced_equipment,
        "top_technicians": top_technicians,
    }
    return render(request, "dashboard/dashboard.html", context)


def equipment_service_ranking(request):
    filter_form = WidgetDateFilterForm(request.GET, prefix="f")
    filter_form.is_valid()
    qs = get_service_ranking_queryset(
        date_from=filter_form.cleaned_data.get("date_from"),
        date_to=filter_form.cleaned_data.get("date_to"),
    )
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)
    return render(
        request, "dashboard/equipment_service_ranking.html",
        {
            "active_page": "dashboard",
            "page_obj": page_obj,
            "filter_form": filter_form,
            "filter_querystring": querydict.urlencode(),
        },
    )


def technician_ranking(request):
    filter_form = WidgetDateFilterForm(request.GET, prefix="f")
    filter_form.is_valid()
    qs = get_technician_ranking_queryset(
        date_from=filter_form.cleaned_data.get("date_from"),
        date_to=filter_form.cleaned_data.get("date_to"),
    )
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)
    return render(
        request, "dashboard/technician_ranking.html",
        {
            "active_page": "dashboard",
            "page_obj": page_obj,
            "filter_form": filter_form,
            "filter_querystring": querydict.urlencode(),
        },
    )