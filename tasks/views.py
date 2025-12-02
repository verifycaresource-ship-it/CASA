from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages

from .models import Task
from .forms import TaskForm


# ==========================================================
# TASK DASHBOARD / LIST
# ==========================================================
@login_required(login_url="accounts:login")
def task_list(request):

    tasks = Task.objects.select_related("assigned_to").all()

    # ====================
    # FILTERS
    # ====================
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    week = request.GET.get("week", "")

    if search:
        tasks = tasks.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(assigned_to__username__icontains=search)
        )

    if status:
        tasks = tasks.filter(status=status)

    if priority:
        tasks = tasks.filter(priority=priority)

    if week:
        tasks = tasks.filter(week=week)

    tasks = tasks.order_by("-created_at")

    # ====================
    # KPI COUNTS
    # ====================
    kpis = {
        "total": Task.objects.count(),
        "pending": Task.objects.filter(status=Task.STATUS_PENDING).count(),
        "progress": Task.objects.filter(status=Task.STATUS_IN_PROGRESS).count(),
        "completed": Task.objects.filter(status=Task.STATUS_COMPLETED).count(),
        "overdue": Task.objects.filter(status=Task.STATUS_OVERDUE).count(),
    }

    # ====================
    # BULK ACTIONS (SAFE)
    # ====================
    if request.method == "POST":

        selected_ids = request.POST.getlist("selected_tasks")
        queryset = Task.objects.filter(id__in=selected_ids)

        # Only perform actions if a button was clicked
        if "complete" in request.POST:
            if queryset.exists():
                queryset.update(status=Task.STATUS_COMPLETED)
                messages.success(request, "✅ Selected tasks marked as completed.")
            else:
                messages.warning(request, "⚠ No tasks selected.")

        elif "delete" in request.POST:
            if queryset.exists():
                queryset.delete()
                messages.success(request, "🗑 Selected tasks deleted.")
            else:
                messages.warning(request, "⚠ No tasks selected.")

        # ✅ Prevent duplicate message stacking
        return redirect("tasks:task_list")

    # ====================
    # PAGINATION
    # ====================
    paginator = Paginator(tasks, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ====================
    # CONTEXT
    # ====================
    context = {

        "tasks": page_obj,
        "page_obj": page_obj,

        "statuses": Task.STATUS_CHOICES,
        "priorities": Task.PRIORITY_CHOICES,

        "filters": {
            "search": search,
            "status": status,
            "priority": priority,
            "week": week,
        },

        "kpis": kpis,
    }

    return render(request, "tasks/task_list.html", context)


# ==========================================================
# TASK CREATE — REDIRECT BACK TO DASHBOARD (LOCKED)
# ==========================================================
@login_required(login_url="accounts:login")
def task_create(request):
    """
    Create a task and redirect back to dashboard.
    """

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = TaskForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "✅ Task created successfully!")

            return redirect(next_url or "tasks:task_list")

    else:
        form = TaskForm()

    return render(request, "tasks/task_form.html", {
        "form": form,
        "next": next_url or "tasks:task_list"
    })


# ==========================================================
# TASK UPDATE
# ==========================================================
@login_required(login_url="accounts:login")
def task_update(request, pk):

    task = get_object_or_404(Task, pk=pk)
    form = TaskForm(request.POST or None, instance=task)

    if form.is_valid():
        form.save()
        messages.success(request, "✅ Task updated successfully!")
        return redirect("tasks:task_list")

    return render(request, "tasks/task_form.html", {
        "form": form,
        "task": task,
        "next": "tasks:task_list"
    })


# ==========================================================
# TASK DELETE
# ==========================================================
@login_required(login_url="accounts:login")
def task_delete(request, pk):

    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        task.delete()
        messages.success(request, "🗑 Task deleted successfully.")
        return redirect("tasks:task_list")

    return render(request, "tasks/task_confirm_delete.html", {
        "task": task
    })
