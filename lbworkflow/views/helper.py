# -*- coding: utf-8 -*-
import importlib

from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from lbworkflow import settings


def import_wf_views(wf_code, view_module_name='views'):
    wf_module = settings.WF_APPS.get(wf_code)
    return importlib.import_module('%s.%s' % (wf_module, view_module_name))


def add_processed_message(request, process_instance, act_descn='Processed'):
    messages.info(
        request,
        'Process "{0}" has been {1}. Current status："{2}" Current user："{3}"'.format(
            process_instance.no, act_descn, process_instance.cur_node.name,
            process_instance.get_operators_display()
        )
    )


def user_wf_info_as_dict(wf_obj, user):
    ctx = {}
    if user.is_anonymous:
        return ctx
    instance = wf_obj.pinstance
    is_wf_admin = instance.is_wf_admin(user)
    in_process = instance.cur_node.status == 'in progress'
    task = instance.get_todo_task(user)
    ctx['wf_code'] = instance.process.code
    ctx['process'] = instance.process
    ctx['process_instance'] = instance
    ctx['object'] = wf_obj
    ctx['task'] = task
    ctx['wf_history'] = instance.event_set.all().order_by('-created_on', '-pk')
    ctx['operators_display'] = instance.get_operators_display()
    ctx['is_wf_admin'] = is_wf_admin

    can_edit = not instance.cur_node.is_submitted() and instance.created_by == user
    can_edit = can_edit or (instance.cur_node.can_edit and task)
    can_edit = can_edit or is_wf_admin
    ctx['can_edit'] = can_edit
    ctx['can_rollback'] = instance.can_rollback(user)

    if in_process:
        ctx['can_assign'] = task or is_wf_admin or user.is_superuser
        ctx['can_remind'] = instance.created_by == user or is_wf_admin
        ctx['can_give_up'] = instance.can_give_up(user)

    if task:
        instance.get_todo_tasks(user).filter(
            receive_on=None
        ).update(receive_on=timezone.now())
        transitions = instance.get_transitions()
        ctx['can_reject'] = instance.cur_node.can_reject
        ctx['can_back_to'] = None
        ctx['transitions'] = transitions
        ctx['agree_transitions'] = instance.get_merged_agree_transitions()
        ctx['other_transitions'] = [e for e in transitions if not e.is_agree]
    # TODO add reject,given up to other_transitions?
    return ctx


def get_base_wf_permit_query_param(user, process_instance_field_prefix='pinstance__'):
    def p(param_name, value):
        return {process_instance_field_prefix + param_name: value}
    q_param = Q()
    # Submit
    q_param = q_param | Q(
        **p('created_by', user)
    )
    # share
    q_param = q_param | Q(
        **p('can_view_users', user)
    )
    # Can process
    q_param = q_param | Q(
        **p('task__user', user)
    )
    q_param = q_param | Q(
        **p('task__agent_user', user)
    )
    return q_param
