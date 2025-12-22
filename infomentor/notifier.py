class CompositeNotifier:
    def __init__(self, notifiers):
        self.notifiers = notifiers

    def send_webhook(
        self,
        summary,
        events,
        highlights,
        news_title,
        attachment_paths=None,
        full_item=None,
    ):
        for notifier in self.notifiers:
            notifier.send_webhook(
                summary, events, highlights, news_title, attachment_paths, full_item
            )

    def send_schedule_update(self, schedule, week_str, is_new_week=False, changes=None):
        for notifier in self.notifiers:
            notifier.send_schedule_update(schedule, week_str, is_new_week, changes)

    def send_notification(self, notification):
        for notifier in self.notifiers:
            notifier.send_notification(notification)

    def send_error(self, context, error_message):
        for notifier in self.notifiers:
            notifier.send_error(context, error_message)
