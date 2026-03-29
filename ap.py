import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client

# --- CONFIGURATION ---
st.set_page_config(page_title="Charbonneur Business", page_icon="🚕", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e6e6f1;
        border-radius: 15px; padding: 20px; box-shadow: 2px 4px 10px rgba(0, 0, 0, 0.08);
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    h1, h2, h3 { color: #1E3A8A; }
    </style>
""", unsafe_allow_html=True)


# --- CONNEXION SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = init_connection()

# --- MENU LATÉRAL ---
with st.sidebar:
    st.markdown("## 🚕 Charbonneur Business")
    st.write("---")
    menu = st.radio("NAVIGATION", ["🏠 Tableau de Bord", "💳 Paiements", "👥 Chauffeurs", "🏍️ Véhicules"],
                    label_visibility="collapsed")
    st.write("---")
    st.info(f"📅 Date : **{datetime.date.today().strftime('%d/%m/%Y')}**")

# ==========================================
# 🏠 1. TABLEAU DE BORD
# ==========================================
if menu == "🏠 Tableau de Bord":
    st.title("Tableau de Bord")

    # KPIs
    paies_data = supabase.table('paiements').select('montant').execute().data
    caisse_totale = sum(p['montant'] for p in paies_data) if paies_data else 0.0

    nb_vehicules = len(supabase.table('vehicules').select('id').execute().data)
    nb_chauffeurs = len(supabase.table('chauffeurs').select('id').execute().data)

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Caisse Totale", f"{int(caisse_totale):,} $".replace(",", " "))
    col2.metric("🏍️ Véhicules en service", nb_vehicules)
    col3.metric("👥 Chauffeurs actifs", nb_chauffeurs)

    st.write("<br>", unsafe_allow_html=True)

    col_graph, col_prog = st.columns([1.5, 1])
    with col_graph:
        st.subheader("📈 Évolution des Recettes")
        p_data = supabase.table('paiements').select('date, montant').execute().data
        if p_data:
            df_paiements = pd.DataFrame(p_data)
            df_paiements['date'] = pd.to_datetime(df_paiements['date'])
            df_paiements = df_paiements.groupby(df_paiements['date'].dt.date)['montant'].sum().reset_index()
            df_paiements.set_index('date', inplace=True)
            st.bar_chart(df_paiements['montant'], color="#3b82f6")
        else:
            st.info("Aucun paiement pour générer le graphique.")

    with col_prog:
        st.subheader("🎯 Objectifs Chauffeurs")
        c_data = supabase.table('chauffeurs').select('id, nom, montant_total').execute().data
        if c_data:
            donnees_tableau = []
            for row in c_data:
                p_chauff = supabase.table('paiements').select('montant').eq('chauffeur_id', row['id']).execute().data
                deja_paye = sum(p['montant'] for p in p_chauff) if p_chauff else 0.0
                prog = int((deja_paye / row['montant_total']) * 100) if row['montant_total'] > 0 else 0
                donnees_tableau.append({"Chauffeur": row['nom'], "Avancement": prog})

            st.dataframe(pd.DataFrame(donnees_tableau), column_config={
                "Avancement": st.column_config.ProgressColumn("Progression (%)", format="%d%%", min_value=0,
                                                              max_value=100)}, hide_index=True,
                         use_container_width=True)
        else:
            st.info("Aucun chauffeur enregistré.")

# ==========================================
# 💳 2. PAIEMENTS
# ==========================================
elif menu == "💳 Paiements":
    st.title("Gestion des Versements")
    tab_ajout, tab_suppr = st.tabs(["💰 Enregistrer un dépôt", "🗑️ Annuler une erreur"])

    c_data = supabase.table('chauffeurs').select('id, nom, versement_hebdo, montant_total').execute().data

    with tab_ajout:
        if not c_data:
            st.warning("Ajoutez d'abord un chauffeur.")
        else:
            with st.container(border=True):
                df_c = pd.DataFrame(c_data)
                options_c = df_c.apply(lambda x: f"{x['id']} - {x['nom']}", axis=1).tolist()
                chauffeur_choisi = st.selectbox("Sélectionner le Chauffeur", options_c, key="ajout_p")
                c_id = int(chauffeur_choisi.split(" - ")[0])

                # Montant déjà payé
                p_chauff = supabase.table('paiements').select('montant').eq('chauffeur_id', c_id).execute().data
                deja_paye = sum(p['montant'] for p in p_chauff) if p_chauff else 0.0

                chauf_info = next(item for item in c_data if item["id"] == c_id)
                reste_a_payer = chauf_info['montant_total'] - deja_paye

                st.success(f"💡 Il reste **{int(reste_a_payer)}$** à payer pour ce chauffeur.")

                with st.form("form_paiement", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    montant = col1.number_input("Montant déposé ($)", min_value=1.0,
                                                value=float(chauf_info['versement_hebdo']))
                    date_paiement = col2.date_input("Date du dépôt", datetime.date.today())

                    if st.form_submit_button("✅ Valider l'encaissement", use_container_width=True):
                        date_str = str(date_paiement)
                        # Vérification doublon
                        verif = supabase.table('paiements').select('id').eq('chauffeur_id', c_id).eq('date',
                                                                                                     date_str).execute().data
                        if verif:
                            st.error("⚠️ Un versement est déjà enregistré à cette date !")
                        elif montant > reste_a_payer:
                            st.error("⚠️ Le montant dépasse la dette restante !")
                        else:
                            supabase.table('paiements').insert(
                                {"chauffeur_id": c_id, "montant": montant, "date": date_str}).execute()
                            st.success("Versement validé avec succès !")
                            st.rerun()

    with tab_suppr:
        p_all = supabase.table('paiements').select('id, montant, date, chauffeurs(nom)').execute().data
        if not p_all:
            st.info("Aucun paiement enregistré.")
        else:
            # Aplatir les données pour l'affichage
            options_p = [f"ID:{p['id']} - {p['chauffeurs']['nom']} - {p['montant']}$ le {p['date']}" for p in p_all]
            paiement_choisi = st.selectbox("Sélectionner le paiement à annuler", options_p)
            p_id = int(paiement_choisi.split(" - ")[0].replace("ID:", ""))

            if st.button("🗑️ Supprimer ce paiement", type="primary"):
                supabase.table('paiements').delete().eq('id', p_id).execute()
                st.success("Paiement supprimé !")
                st.rerun()

# ==========================================
# 👥 3. CHAUFFEURS
# ==========================================
elif menu == "👥 Chauffeurs":
    st.title("Gestion des Chauffeurs")
    tab_liste, tab_ajout, tab_edit = st.tabs(["📋 Liste", "➕ Ajouter", "✏️ Modifier / Supprimer"])

    with tab_liste:
        liste_c = supabase.table('chauffeurs').select(
            'id, nom, contact, montant_total, vehicules(plaque)').execute().data
        if not liste_c:
            st.info("Aucun chauffeur.")
        else:
            for d in liste_c:
                d['Moto Assignée'] = d['vehicules']['plaque'] if d['vehicules'] else "Aucune"
                del d['vehicules']
            st.dataframe(pd.DataFrame(liste_c), hide_index=True, use_container_width=True)

    with tab_ajout:
        tous_v = supabase.table('vehicules').select('id, type, plaque').execute().data
        c_assignes = supabase.table('chauffeurs').select('vehicule_id').execute().data
        ids_assignes = [c['vehicule_id'] for c in c_assignes if c['vehicule_id']]

        v_libres = [v for v in tous_v if v['id'] not in ids_assignes]

        if not v_libres:
            st.warning("⚠️ Enregistrez un véhicule libre d'abord.")
        else:
            with st.form("form_chauffeur", clear_on_submit=True):
                options_v = [f"{v['id']} - {v['type']} ({v['plaque']})" for v in v_libres]
                col1, col2 = st.columns(2)
                nom = col1.text_input("Nom complet*")
                contact = col2.text_input("Téléphone")
                vehicule_choisi = col1.selectbox("Assigner un véhicule", options_v)
                col3, col4 = st.columns(2)
                duree = col3.number_input("Durée (mois)", min_value=1, value=6)
                montant_hebdo = col4.number_input("Versement hebdo ($)", min_value=1.0, value=100.0)

                if st.form_submit_button("Sauvegarder", use_container_width=True) and nom.strip():
                    v_id = int(vehicule_choisi.split(" - ")[0])
                    montant_total = duree * 4 * montant_hebdo
                    supabase.table('chauffeurs').insert(
                        {"nom": nom, "contact": contact, "vehicule_id": v_id, "duree_mois": duree,
                         "montant_total": montant_total, "versement_hebdo": montant_hebdo}).execute()
                    st.success("Chauffeur ajouté ! ✅")
                    st.rerun()

    with tab_edit:
        c_edit_data = supabase.table('chauffeurs').select('id, nom, contact').execute().data
        if not c_edit_data:
            st.info("Aucun chauffeur à modifier.")
        else:
            options_c_edit = [f"{c['id']} - {c['nom']}" for c in c_edit_data]
            c_choisi = st.selectbox("Sélectionner un chauffeur", options_c_edit)
            c_edit_id = int(c_choisi.split(" - ")[0])

            infos = next(item for item in c_edit_data if item["id"] == c_edit_id)

            with st.form("form_edit_c"):
                new_nom = st.text_input("Nom", value=infos['nom'])
                new_contact = st.text_input("Téléphone", value=infos['contact'])

                col_upd, col_del = st.columns(2)
                if col_upd.form_submit_button("💾 Mettre à jour", use_container_width=True):
                    supabase.table('chauffeurs').update({"nom": new_nom, "contact": new_contact}).eq("id",
                                                                                                     c_edit_id).execute()
                    st.success("Profil mis à jour !")
                    st.rerun()

                if col_del.form_submit_button("❌ Supprimer le chauffeur", use_container_width=True):
                    supabase.table('chauffeurs').delete().eq("id", c_edit_id).execute()
                    st.error("Chauffeur supprimé !")
                    st.rerun()

# ==========================================
# 🏍️ 4. VÉHICULES
# ==========================================
elif menu == "🏍️ Véhicules":
    st.title("Flotte de Véhicules")
    tab_liste, tab_ajout, tab_edit = st.tabs(["📋 Liste", "➕ Ajouter", "✏️ Modifier / Supprimer"])

    with tab_liste:
        v_data = supabase.table('vehicules').select('*').execute().data
        if not v_data:
            st.info("Votre flotte est vide.")
        else:
            st.dataframe(pd.DataFrame(v_data), hide_index=True, use_container_width=True)

    with tab_ajout:
        with st.form("form_vehicule", clear_on_submit=True):
            col1, col2 = st.columns(2)
            type_v = col1.selectbox("Type de véhicule", ["Moto", "Voiture", "Tricycle"])
            plaque = col2.text_input("Plaque*")
            moteur = col1.text_input("Moteur*")
            couleur = col2.text_input("Couleur")
            if st.form_submit_button("Enregistrer", use_container_width=True) and plaque.strip() and moteur.strip():
                supabase.table('vehicules').insert(
                    {"type": type_v, "plaque": plaque, "moteur": moteur, "couleur": couleur}).execute()
                st.success("Véhicule ajouté ! ✅")
                st.rerun()

    with tab_edit:
        v_edit_data = supabase.table('vehicules').select('id, plaque, type, moteur, couleur').execute().data
        if not v_edit_data:
            st.info("Aucun véhicule à modifier.")
        else:
            options_v_edit = [f"{v['id']} - {v['type']} ({v['plaque']})" for v in v_edit_data]
            v_choisi = st.selectbox("Sélectionner un véhicule", options_v_edit)
            v_edit_id = int(v_choisi.split(" - ")[0])

            infos_v = next(item for item in v_edit_data if item["id"] == v_edit_id)

            with st.form("form_edit_v"):
                new_plaque = st.text_input("Plaque", value=infos_v['plaque'])
                new_moteur = st.text_input("Moteur", value=infos_v['moteur'])
                new_couleur = st.text_input("Couleur", value=infos_v['couleur'])

                col_upd, col_del = st.columns(2)
                if col_upd.form_submit_button("💾 Mettre à jour", use_container_width=True):
                    supabase.table('vehicules').update(
                        {"plaque": new_plaque, "moteur": new_moteur, "couleur": new_couleur}).eq("id",
                                                                                                 v_edit_id).execute()
                    st.success("Véhicule mis à jour !")
                    st.rerun()

                if col_del.form_submit_button("❌ Supprimer le véhicule", use_container_width=True):
                    # Vérifier si assigné
                    verif = supabase.table('chauffeurs').select('id').eq('vehicule_id', v_edit_id).execute().data
                    if verif:
                        st.error("⚠️ Impossible : ce véhicule est assigné à un chauffeur !")
                    else:
                        supabase.table('vehicules').delete().eq("id", v_edit_id).execute()
                        st.success("Véhicule supprimé !")
                        st.rerun()