PLAN_SELECTIONS = {}


def set_plan(user_id, plan_type):
    PLAN_SELECTIONS[user_id] = plan_type
    return plan_type


def get_plan(user_id):
    return PLAN_SELECTIONS.get(user_id)
