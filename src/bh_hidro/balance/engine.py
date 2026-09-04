"""FAO daily soil-water bucket. Ported later from balance_hidrico_pandarized."""


class BalanceEngine:
    """Placeholder: sequential daily balance per formita.

    Needs yesterday's almacenaje; precip/ETP come from ingest tables
    with source priority (IMERG → ERALand → WRF).
    """

    def run(self, *args, **kwargs):
        raise NotImplementedError("Transfer from bhERA5 BalanceEngine")
