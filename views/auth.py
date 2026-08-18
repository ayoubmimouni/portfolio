# -*- coding: utf-8 -*-
"""Signed-out screen.

Not a page: rendered by `app.py` in place of the whole shell when the session
is signed out. No credentials are collected — this is a demo workspace, so
signing back in is a single confirmation.
"""

from __future__ import annotations

import streamlit as st

from services import store
from ui import components as c
from ui.icons import icon_html, st_icon


def signed_out_screen() -> None:
    st.write("")
    columns = st.columns([1, 1.5, 1])
    with columns[1]:
        with c.card("hero", key="signout"):
            c.render(
                '<div style="text-align:center;padding:0.5rem 0 0.25rem">'
                '<span class="opt-brand__mark" style="width:3rem;height:3rem;margin:0 auto">'
                f'{icon_html("markets", size="1.5rem")}</span>'
                '<div style="font-size:var(--opt-fs-2xl);font-weight:750;letter-spacing:-0.02em;'
                'margin-top:0.75rem">Session terminée</div>'
                '<div class="opt-page__sub" style="margin:0.375rem auto 0">'
                "Vous êtes déconnecté d'Optiport. Vos préférences et votre "
                "liste de suivi sont conservées pour cette session.</div></div>"
            )
            st.write("")
            if st.button("Revenir à la plateforme", type="primary", width="stretch",
                         icon=st_icon("logout"), key="sign_back_in"):
                store.sign_in()
                st.rerun()
            c.caption(
                "Espace de démonstration : aucun mot de passe n'est demandé et "
                "aucune donnée personnelle n'est transmise."
            )
