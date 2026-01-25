from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone

from .models import Task
from .forms import TaskForm


@login_required(login_url="accounts:login")
def task_list(request):
    """List tasks with filters, KPI, pagination, and bulk actions."""
    tasks = Task.objects.select_related("assigned_to").all()

    # ----------------- FILTERS -----------------
    search = request.GET.get("search", "")
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    week = request.GET.get("week", "")

    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(assigned_to__username__icontains=search)
        )
    if status:
        tasks = tasks.filter(status=status)
    if priority:
        tasks = tasks.filter(priority=priority)
    if week:
        tasks = tasks.filter(week=week)

    tasks = tasks.order_by("-created_at")

    # ----------------- KPI -----------------
    kpis = {
        "Total": Task.objects.count(),
        "Pending": Task.objects.filter(status=Task.STATUS_PENDING).count(),
        "In Progress": Task.objects.filter(status=Task.STATUS_IN_PROGRESS).count(),
        "Completed": Task.objects.filter(status=Task.STATUS_COMPLETED).count(),
        "Overdue": Task.objects.filter(status=Task.STATUS_OVERDUE).count(),
    }

    # ----------------- BULK ACTIONS -----------------
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_tasks")
        if not selected_ids:
            messages.warning(request, "No tasks selected.")
            return redirect("tasks:task_list")

        selected_tasks = Task.objects.filter(id__in=selected_ids)

        if "delete" in request.POST:
            selected_tasks.delete()
            messages.success(request, "Selected tasks deleted successfully.")
        elif "complete" in request.POST:
            for t in selected_tasks:
                t.status = Task.STATUS_COMPLETED
                t.save()
            messages.success(request, "Selected tasks marked as completed.")

        return redirect("tasks:task_list")

    # ----------------- PAGINATION -----------------
    paginator = Paginator(tasks, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "tasks/task_list.html", {
        "tasks": page_obj,
        "page_obj": page_obj,
        "statuses": Task.STATUS_CHOICES,
        "priorities": Task.PRIORITY_CHOICES,
        "filters": {"search": search, "status": status, "priority": priority, "week": week},
        "kpis": kpis,
    })


@login_required(login_url="accounts:login")
def task_create(request):
    """Create a new task and redirect to dashboard."""
    next_url = request.GET.get("next") or request.POST.get("next") or "tasks:task_list"

    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Task created successfully!")
            return redirect(next_url)
    else:
        form = TaskForm()

    return render(request, "tasks/task_form.html", {"form": form, "mode": "create"})


@login_required(login_url="accounts:login")
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    form = TaskForm(request.POST or None, instance=task)

    if form.is_valid():
        form.save()
        messages.success(request, "Task updated successfully.")
        return redirect("tasks:task_list")

    return render(request, "tasks/task_form.html", {"form": form, "mode": "edit"})


@login_required(login_url="accounts:login")
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted successfully.")
        return redirect("tasks:task_list")

    return render(request, "tasks/task_confirm_delete.html", {"task": task})
