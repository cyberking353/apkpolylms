from django.contrib import admin
from django import forms
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html
from .models import Exam, ExamQuestion, ExamChoice, ExamAttempt, ExamViolation


class ExamAdminForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        open_at  = cleaned.get('open_at')
        close_at = cleaned.get('close_at')
        if open_at and close_at and close_at <= open_at:
            raise forms.ValidationError('Close time must be after open time.')
        return cleaned


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    form = ExamAdminForm
    list_display  = ('__str__', 'course', 'exam_status', 'open_at', 'close_at',
                     'time_limit_minutes', 'pass_mark', 'is_active', 'question_count', 'manage_link')
    list_filter   = ('exam_status', 'is_active', 'course__level', 'course__semester')
    search_fields = ('title', 'course__title')
    fieldsets = (
        (None, {'fields': ('course', 'title', 'instructions')}),
        ('Workflow', {
            'fields': ('exam_status', 'review_note'),
            'description': 'Lecturer submits for approval. Once you approve, set the schedule below.'
        }),
        ('Schedule & Rules (set when approving)', {
            'fields': ('open_at', 'close_at', 'time_limit_minutes', 'pass_mark', 'is_active'),
            'description': 'open_at and close_at can be left blank until you are ready to schedule the exam.'
        }),
        ('Proctoring', {
            'fields': ('enable_proctoring', 'max_violations'),
            'description': 'Fullscreen + tab-switch monitoring, single active session, auto-submit on excess violations.'
        }),
    )
    actions = ['approve_and_schedule', 'send_back_to_lecturer']

    @admin.action(description='✓ Approve selected exams (you must then set the schedule on each)')
    def approve_and_schedule(self, request, queryset):
        count = queryset.filter(exam_status='pending').update(exam_status='approved')
        self.message_user(request,
            f"Approved {count} exam(s). Open each one to set open_at and close_at.",
            level=messages.SUCCESS)

    @admin.action(description='✗ Send back to lecturer (sets status back to draft)')
    def send_back_to_lecturer(self, request, queryset):
        count = queryset.update(exam_status='draft')
        self.message_user(request, f"Sent {count} exam(s) back to draft.", level=messages.WARNING)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:exam_id>/manage-questions/', self.admin_site.admin_view(self.manage_questions),
                 name='exams_exam_manage_questions'),
        ]
        return custom + urls

    def manage_link(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('admin:exams_exam_manage_questions', args=[obj.pk])
        return format_html('<a class="button" href="{}">📝 Manage Questions &amp; Answers</a>', url)
    manage_link.short_description = 'Questions'

    def manage_questions(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        if request.method == 'POST':
            self._save_questions(request, exam)
            messages.success(request, 'Questions and answers saved.')
            return redirect(reverse('admin:exams_exam_manage_questions', args=[exam.pk]))
        questions = list(exam.questions.prefetch_related('choices').all())
        for q in questions:
            choices = list(q.choices.all())
            while len(choices) < 4:
                choices.append(None)
            q.padded_choices = choices[:4]
        blank_rows = 3 if not questions else 1
        context = {
            **self.admin_site.each_context(request),
            'title': f'Questions & Answers — {exam}',
            'exam': exam, 'questions': questions,
            'blank_rows': range(blank_rows), 'choice_range': range(4),
            'opts': self.model._meta,
        }
        return render(request, 'admin/exams/manage_questions.html', context)

    def _save_questions(self, request, exam):
        existing_ids = {str(q.id) for q in exam.questions.all()}
        posted_keys = {k[len('question_'):] for k in request.POST if k.startswith('question_')}
        order = 1
        for rowkey in sorted(posted_keys, key=lambda k: (k.startswith('new'), k)):
            text = request.POST.get(f'question_{rowkey}', '').strip()
            if not text:
                continue
            if rowkey in existing_ids:
                q = ExamQuestion.objects.get(id=rowkey, exam=exam)
                q.text = text; q.order = order; q.save()
            else:
                q = ExamQuestion.objects.create(exam=exam, text=text, order=order)
            correct_idx_raw = request.POST.get(f'correct_{rowkey}')
            correct_idx = int(correct_idx_raw) if correct_idx_raw and correct_idx_raw.isdigit() else None
            q.choices.all().delete()
            for i in range(4):
                ct = request.POST.get(f'choice_{rowkey}_{i}', '').strip()
                if ct:
                    ExamChoice.objects.create(question=q, text=ct, is_correct=(correct_idx == i), order=i)
            order += 1
        delete_ids = request.POST.getlist('delete_question')
        if delete_ids:
            ExamQuestion.objects.filter(id__in=delete_ids, exam=exam).delete()


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display  = ('student', 'exam', 'score', 'passed', 'auto_submitted', 'violation_count',
                     'terminated_reason', 'started_at', 'submitted_at')
    list_filter   = ('passed', 'auto_submitted', 'terminated_reason', 'exam')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'exam__course__title')


@admin.register(ExamViolation)
class ExamViolationAdmin(admin.ModelAdmin):
    list_display  = ('attempt', 'violation_type', 'created_at')
    list_filter   = ('violation_type',)
    search_fields = ('attempt__student__email', 'attempt__exam__course__title')
