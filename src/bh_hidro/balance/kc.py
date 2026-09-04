"""Kc strategies. Calendar (cron) vs GDD (user sowing date)."""

from abc import ABC, abstractmethod


class KcStrategy(ABC):
    @abstractmethod
    def kc_for_date(self, *args, **kwargs):
        raise NotImplementedError


class CalendarKc(KcStrategy):
    """Julian-day mean phenology from patron_kc / rel_etapa_patron."""

    def kc_for_date(self, *args, **kwargs):
        raise NotImplementedError("Transfer from bhERA5 crop_manager")


class GddKc(KcStrategy):
    """Growing-degree-day stages from sowing date + gdd_por_nodo_etapa."""

    def kc_for_date(self, *args, **kwargs):
        raise NotImplementedError("Transfer from bhERA5 CustomBalanceCalculator")
