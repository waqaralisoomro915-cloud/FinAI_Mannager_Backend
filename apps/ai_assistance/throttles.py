from rest_framework.throttling import UserRateThrottle


class SpendingInsightThrottle(UserRateThrottle):
    scope = "spending_insights"
    rate = "10/hour"