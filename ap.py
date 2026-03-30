import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client
import plotly.express as px

# --- CONFIGURATION ---
st.set_page_config(page_title="Charbonneur Business", page_icon="🚕", layout="wide", initial_sidebar_state="collapsed")

# --- DESIGN SPÉCIAL MOBILE (CSS) ---
st.markdown("""
    <style>
    [data-testid="collapsedControl"] { display: none; }
    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;}
    
    .stRadio > div { gap: 10px !important; justify-content: center; flex-wrap: wrap; }
    .stRadio p { font-size: 16px !important; font-weight: 800 !important; color: #1E3A8A; padding: 10px 15px; background-color: #f0f2f6; border-radius: 12px; margin: 0; }
    .stRadio p:active { background-color: #d1d5db; }
    
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e6e6f1; border-radius: 15px; padding: 15px; box-shadow: 2px 4px 10px rgba(0, 0, 0, 0.08); }
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

# ==========================================
# 📱 EN-TÊTE ET NAVIGATION
# ==========================================
st.markdown("<h1 style='text-align: center; margin-top: -50px;'>🚕 Charbonneur Business</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray; font-weight: bold;'>📅 {datetime.date.today().strftime('%d/%m/%Y')}</p>", unsafe_allow_html=True)

menu = st.radio("NAVIGATION", ["🏠 Dashboard", "💳 Paiements", "👥 Chauffeurs", "🏍️ Véhicules"], horizontal=True, label_visibility="collapsed")
st.write("---")

# ==========================================
# 🏠 1. TABLEAU DE BORD (DASHBOARD)
# ==========================================
if menu == "🏠 Dashboard":
    paies_data = supabase.table('paiements').select('montant').execute().data
    caisse_totale = sum(p['montant'] for p in paies_data) if paies_data else 0.0
    nb_vehicules = len(supabase.table('vehicules').select('id').execute().data)
    nb_chauffeurs = len(supabase.table('chauffeurs').select('id').execute().data)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Caisse Totale", f"{int(caisse_totale):,} $".replace(",", " "))
    col2.metric("🏍️ Véhicules", nb_vehicules)
    col3.metric("👥 Chauffeurs", nb_chauffeurs)
    
    st.write("---")
    col_graph, col_hist = st.columns([1.5, 1])
    
    with col_graph:
        st.subheader("📈 Évolution des Recettes")
        p_data = supabase.table('paiements').select('date, montant').execute().data
        if p_data:
            df_paiements = pd.DataFrame(p_data)
            df_paiements['date'] = pd.to_datetime(df_paiements['date'])
            df_paiements = df_paiements.groupby(df_paiements['date'].dt.date)['montant'].sum().reset_index()
            fig = px.area(df_paiements, x='date', y='montant', labels={'date': '', 'montant': 'Revenus ($)'}, markers=True)
            fig.update_traces(line_color='#3b82f6', fillcolor='rgba(59, 130, 246, 0.2)')
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#e6e6f1'), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Aucun paiement pour générer le graphique.")

    with col_hist:
        st.subheader("🕒 Derniers Versements")
        hist_data = supabase.table('paiements').select('date, montant, chauffeurs(nom)').order('date', desc=True).limit(7).execute().data
        if hist_data:
            for p in hist_data:
                nom = p['chauffeurs']['nom'] if p['chauffeurs'] else "Inconnu"
                st.markdown(f"**{p['date']}** : ✅ **{p['montant']}$** ({nom})")
        else:
            st.info("Aucun historique récent.")

# ==========================================
# 💳 2. PAIEMENTS
# ==========================================
elif menu == "💳 Paiements":
    st.title("Saisie des Versements")
    tab_ajout, tab_suppr = st.tabs(["💰 Enregistrer", "🗑️ Annuler"])
    c_data = supabase.table('chauffeurs').select('id, nom, versement_hebdo, montant_total').execute().data
    
    with tab_ajout:
        if not c_data: st.warning("Ajoutez d'abord un chauffeur.")
        else:
            with st.container(border=True):
                options_c = pd.DataFrame(c_data).apply(lambda x: f"{x['id']} - {x['nom']}", axis=1).tolist()
                chauffeur_choisi = st.selectbox("Sélectionner le Chauffeur", options_c)
                c_id = int(chauffeur_choisi.split(" - ")[0])
                
                p_chauff = supabase.table('paiements').select('montant').eq('chauffeur_id', c_id).execute().data
                deja_paye = sum(p['montant'] for p in p_chauff) if p_chauff else 0.0
                chauf_info = next(item for item in c_data if item["id"] == c_id)
                reste_a_payer = chauf_info['montant_total'] - deja_paye
                
                st.success(f"💡 Il reste **{int(reste_a_payer)}$** à payer.")
                
                with st.form("form_paiement", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    montant = col1.number_input("Montant déposé ($)", min_value=1.0, value=float(chauf_info['versement_hebdo']))
                    date_paiement = col2.date_input("Date du dépôt", datetime.date.today())
                    
                    if st.form_submit_button("✅ Valider l'encaissement", use_container_width=True):
                        date_str = str(date_paiement)
                        if supabase.table('paiements').select('id').eq('chauffeur_id', c_id).eq('date', date_str).execute().data:
                            st.error("⚠️ Un versement est déjà enregistré à cette date !")
                        elif montant > reste_a_payer:
                            st.error("⚠️ Le montant dépasse la dette !")
                        else:
                            supabase.table('paiements').insert({"chauffeur_id": c_id, "montant": montant, "date": date_str}).execute()
                            st.success("Versement validé !")
                            st.rerun()

    with tab_suppr:
        p_all = supabase.table('paiements').select('id, montant, date, chauffeurs(nom)').order('date', desc=True).execute().data
        if not p_all: st.info("Aucun paiement.")
        else:
            options_p = [f"ID:{p['id']} - {p['chauffeurs']['nom']} - {p['montant']}$ le {p['date']}" for p in p_all]
            p_id = int(st.selectbox("Sélectionner", options_p).split(" - ")[0].replace("ID:", ""))
            if st.button("🗑️ Supprimer l'erreur", type="primary", use_container_width=True):
                supabase.table('paiements').delete().eq('id', p_id).execute()
                st.success("Supprimé !")
                st.rerun()

# ==========================================
# 👥 3. CHAUFFEURS (PROFIL MIS À JOUR)
# ==========================================
elif menu == "👥 Chauffeurs":
    st.title("Chauffeurs")
    tab_liste, tab_profil, tab_ajout, tab_edit = st.tabs(["📋 Liste", "👤 Profil", "➕ Ajouter", "✏️ Modifier"])
    
    with tab_liste:
        liste_c = supabase.table('chauffeurs').select('id, nom, contact, montant_total, vehicules(plaque)').execute().data
        if not liste_c: st.info("Aucun chauffeur.")
        else:
            for d in liste_c:
                d['Moto'] = d['vehicules']['plaque'] if d['vehicules'] else "Aucune"
                del d['vehicules']
            st.dataframe(pd.DataFrame(liste_c), hide_index=True, use_container_width=True)

    with tab_profil:
        c_profil_data = supabase.table('chauffeurs').select('id, nom, contact, montant_total, versement_hebdo, vehicules(type, plaque)').execute().data
        if not c_profil_data: st.info("Ajoutez des chauffeurs.")
        else:
            c_choisi = st.selectbox("Inspecter un profil", [f"{c['id']} - {c['nom']}" for c in c_profil_data])
            cp_id = int(c_choisi.split(" - ")[0])
            infos = next(item for item in c_profil_data if item["id"] == cp_id)
            
            historique_chauf = supabase.table('paiements').select('date, montant').eq('chauffeur_id', cp_id).order('date', desc=True).execute().data
            deja_paye = sum(p['montant'] for p in historique_chauf) if historique_chauf else 0.0
            reste = infos['montant_total'] - deja_paye
            progression = int((deja_paye / infos['montant_total']) * 100) if infos['montant_total'] > 0 else 0
            
            # --- CALCUL DE LA DATE DE DÉBUT ---
            if historique_chauf:
                # Le premier paiement est le dernier élément de la liste (car classée du plus récent au plus ancien)
                date_debut_brute = historique_chauf[-1]['date']
                date_debut = datetime.datetime.strptime(date_debut_brute, "%Y-%m-%d").strftime("%d/%m/%Y")
            else:
                date_debut = "Aucun versement"

            statut_badge = "⚪ Nouveau"
            if reste <= 0: statut_badge = "🎉 Terminé"
            elif historique_chauf:
                jours_ecoules = (datetime.date.today() - datetime.datetime.strptime(historique_chauf[0]['date'], "%Y-%m-%d").date()).days
                if jours_ecoules <= 7: statut_badge = "🟢 À jour"
                elif jours_ecoules <= 14: statut_badge = f"🟡 Retard ({jours_ecoules} jrs)"
                else: statut_badge = f"🔴 Alerte Rouge ({jours_ecoules} jrs)"

            with st.container(border=True):
                st.subheader(f"{infos['nom']} ({statut_badge})")
                moto = f"{infos['vehicules']['type']} ({infos['vehicules']['plaque']})" if infos['vehicules'] else "Aucune moto"
                st.write(f"📞 {infos['contact']} | 🏍️ {moto}")
                
                st.write("---")
                
                # --- LES TROIS GROS BLOCS VISUELS ---
                colA, colB, colC = st.columns(3)
                colA.metric("🗓️ Début", date_debut)
                colB.metric("✅ Déjà donné", f"{int(deja_paye)} $")
                colC.metric("⏳ Reste", f"{int(reste)} $")
                
                st.progress(progression / 100, text=f"Avancement : {progression}% (Total attendu : {infos['montant_total']}$)")
            
            if historique_chauf:
                st.markdown("#### 📜 Historique personnel")
                st.dataframe(pd.DataFrame(historique_chauf), hide_index=True, use_container_width=True)

    with tab_ajout:
        tous_v = supabase.table('vehicules').select('id, type, plaque').execute().data
        ids_assignes = [c['vehicule_id'] for c in supabase.table('chauffeurs').select('vehicule_id').execute().data if c['vehicule_id']]
        v_libres = [v for v in tous_v if v['id'] not in ids_assignes]
        
        if not v_libres: st.warning("⚠️ Enregistrez une moto libre d'abord.")
        else:
            with st.form("form_chauffeur", clear_on_submit=True):
                nom = st.text_input("Nom complet*")
                contact = st.text_input("Téléphone")
                vehicule_choisi = st.selectbox("Assigner un véhicule", [f"{v['id']} - {v['type']} ({v['plaque']})" for v in v_libres])
                duree = st.number_input("Durée (mois)", min_value=1, value=6)
                montant_hebdo = st.number_input("Versement hebdo ($)", min_value=1.0, value=100.0)
                montant_total = st.number_input("Somme Totale ($)*", min_value=1.0, value=2400.0, step=100.0)
                
                if st.form_submit_button("Sauvegarder", use_container_width=True) and nom.strip():
                    supabase.table('chauffeurs').insert({"nom": nom, "contact": contact, "vehicule_id": int(vehicule_choisi.split(" - ")[0]), "duree_mois": duree, "montant_total": montant_total, "versement_hebdo": montant_hebdo}).execute()
                    st.success("Ajouté ! ✅")
                    st.rerun()

    with tab_edit:
        c_edit_data = supabase.table('chauffeurs').select('id, nom, contact, montant_total').execute().data
        if c_edit_data:
            c_edit_id = int(st.selectbox("Sélectionner", [f"{c['id']} - {c['nom']}" for c in c_edit_data]).split(" - ")[0])
            infos_edit = next(item for item in c_edit_data if item["id"] == c_edit_id)
            with st.form("form_edit_c"):
                new_nom = st.text_input("Nom", value=infos_edit['nom'])
                new_contact = st.text_input("Téléphone", value=infos_edit['contact'])
                new_total = st.number_input("Montant Total ($)", min_value=1.0, value=float(infos_edit['montant_total']))
                if st.form_submit_button("💾 Mettre à jour", use_container_width=True):
                    supabase.table('chauffeurs').update({"nom": new_nom, "contact": new_contact, "montant_total": new_total}).eq("id", c_edit_id).execute()
                    st.success("Mis à jour !")
                    st.rerun()
                if st.form_submit_button("❌ Supprimer", use_container_width=True):
                    supabase.table('chauffeurs').delete().eq("id", c_edit_id).execute()
                    st.error("Supprimé !")
                    st.rerun()

# ==========================================
# 🏍️ 4. VÉHICULES
# ==========================================
elif menu == "🏍️ Véhicules":
    st.title("Flotte")
    tab_liste, tab_ajout, tab_edit = st.tabs(["📋 Liste", "➕ Ajouter", "✏️ Modifier"])
    
    with tab_liste:
        v_data = supabase.table('vehicules').select('*').execute().data
        if not v_data: st.info("Vide.")
        else: st.dataframe(pd.DataFrame(v_data), hide_index=True, use_container_width=True)

    with tab_ajout:
        with st.form("form_vehicule", clear_on_submit=True):
            type_v = st.selectbox("Type", ["Moto", "Voiture", "Tricycle"])
            plaque = st.text_input("Plaque*")
            moteur = st.text_input("Moteur*")
            couleur = st.text_input("Couleur")
            if st.form_submit_button("Enregistrer", use_container_width=True) and plaque.strip() and moteur.strip():
                supabase.table('vehicules').insert({"type": type_v, "plaque": plaque, "moteur": moteur, "couleur": couleur}).execute()
                st.success("Ajouté ! ✅")
                st.rerun()

    with tab_edit:
        v_edit_data = supabase.table('vehicules').select('id, plaque, type, moteur, couleur').execute().data
        if v_edit_data:
            v_edit_id = int(st.selectbox("Sélectionner", [f"{v['id']} - {v['type']} ({v['plaque']})" for v in v_edit_data]).split(" - ")[0])
            infos_v = next(item for item in v_edit_data if item["id"] == v_edit_id)
            with st.form("form_edit_v"):
                new_plaque = st.text_input("Plaque", value=infos_v['plaque'])
                new_moteur = st.text_input("Moteur", value=infos_v['moteur'])
                new_couleur = st.text_input("Couleur", value=infos_v['couleur'])
                if st.form_submit_button("💾 Mettre à jour", use_container_width=True):
                    supabase.table('vehicules').update({"plaque": new_plaque, "moteur": new_moteur, "couleur": new_couleur}).eq("id", v_edit_id).execute()
                    st.success("Mis à jour !")
                    st.rerun()
                if st.form_submit_button("❌ Supprimer", use_container_width=True):
                    if supabase.table('chauffeurs').select('id').eq('vehicule_id', v_edit_id).execute().data:
                        st.error("⚠️ Impossible : assigné à un chauffeur !")
                    else:
                        supabase.table('vehicules').delete().eq("id", v_edit_id).execute()
                        st.success("Supprimé !")
                        st.rerun()
