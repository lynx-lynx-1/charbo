import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client
import plotly.express as px  # <-- La nouvelle bibliothèque magique pour les graphiques !

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
    menu = st.radio("NAVIGATION", ["🏠 Tableau de Bord", "💳 Paiements", "👥 Chauffeurs", "🏍️ Véhicules"], label_visibility="collapsed")
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
    
    st.write("---")
    
    col_graph, col_hist = st.columns([1.5, 1])
    
    with col_graph:
        st.subheader("📈 Évolution des Recettes")
        p_data = supabase.table('paiements').select('date, montant').execute().data
        if p_data:
            df_paiements = pd.DataFrame(p_data)
            df_paiements['date'] = pd.to_datetime(df_paiements['date'])
            df_paiements = df_paiements.groupby(df_paiements['date'].dt.date)['montant'].sum().reset_index()
            
            # --- LE NOUVEAU GRAPHIQUE PLOTLY (Optimisé pour Mobile) ---
            fig = px.area(df_paiements, x='date', y='montant', 
                          labels={'date': '', 'montant': 'Revenus ($)'},
                          markers=True) # Ajoute des petits points sur la courbe
            
            # Personnalisation du design
            fig.update_traces(line_color='#3b82f6', fillcolor='rgba(59, 130, 246, 0.2)')
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), # Supprime les marges inutiles sur téléphone
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#e6e6f1'),
                hovermode="x unified" # Bulle d'info super élégante quand on touche l'écran
            )
            # Affichage en demandant de prendre toute la largeur disponible
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
        else:
            st.info("Aucun paiement pour générer le graphique.")

    with col_hist:
        st.subheader("🕒 Derniers Versements")
        hist_data = supabase.table('paiements').select('date, montant, chauffeurs(nom)').order('date', desc=True).limit(7).execute().data
        
        if hist_data:
            for p in hist_data:
                nom = p['chauffeurs']['nom'] if p['chauffeurs'] else "Chauffeur inconnu"
                st.markdown(f"**{p['date']}** : ✅ **{p['montant']}$** déposés par {nom}")
        else:
            st.info("Aucun historique récent.")

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
                chauffeur_choisi = st.selectbox("Sélectionner le Chauffeur", options_c)
                c_id = int(chauffeur_choisi.split(" - ")[0])
                
                p_chauff = supabase.table('paiements').select('montant').eq('chauffeur_id', c_id).execute().data
                deja_paye = sum(p['montant'] for p in p_chauff) if p_chauff else 0.0
                
                chauf_info = next(item for item in c_data if item["id"] == c_id)
                reste_a_payer = chauf_info['montant_total'] - deja_paye
                
                st.success(f"💡 Il reste **{int(reste_a_payer)}$** à payer pour ce chauffeur.")
                
                with st.form("form_paiement", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    montant = col1.number_input("Montant déposé ($)", min_value=1.0, value=float(chauf_info['versement_hebdo']))
                    date_paiement = col2.date_input("Date du dépôt", datetime.date.today())
                    
                    if st.form_submit_button("✅ Valider l'encaissement", use_container_width=True):
                        date_str = str(date_paiement)
                        verif = supabase.table('paiements').select('id').eq('chauffeur_id', c_id).eq('date', date_str).execute().data
                        if verif:
                            st.error("⚠️ Un versement est déjà enregistré à cette date !")
                        elif montant > reste_a_payer:
                            st.error("⚠️ Le montant dépasse la dette restante !")
                        else:
                            supabase.table('paiements').insert({"chauffeur_id": c_id, "montant": montant, "date": date_str}).execute()
                            st.success("Versement validé avec succès !")
                            st.rerun()

    with tab_suppr:
        p_all = supabase.table('paiements').select('id, montant, date, chauffeurs(nom)').order('date', desc=True).execute().data
        if not p_all:
            st.info("Aucun paiement enregistré.")
        else:
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
    
    tab_liste, tab_profil, tab_ajout, tab_edit = st.tabs(["📋 Liste", "👤 Profil Chauffeur", "➕ Ajouter", "✏️ Modifier"])
    
    with tab_liste:
        liste_c = supabase.table('chauffeurs').select('id, nom, contact, montant_total, vehicules(plaque)').execute().data
        if not liste_c:
            st.info("Aucun chauffeur.")
        else:
            for d in liste_c:
                d['Moto Assignée'] = d['vehicules']['plaque'] if d['vehicules'] else "Aucune"
                del d['vehicules']
            st.dataframe(pd.DataFrame(liste_c), hide_index=True, use_container_width=True)

    with tab_profil:
        c_profil_data = supabase.table('chauffeurs').select('id, nom, contact, montant_total, versement_hebdo, vehicules(type, plaque)').execute().data
        if not c_profil_data:
            st.info("Ajoutez des chauffeurs pour voir leurs profils.")
        else:
            options_profil = [f"{c['id']} - {c['nom']}" for c in c_profil_data]
            choix_profil = st.selectbox("Sélectionner un profil à inspecter", options_profil)
            cp_id = int(choix_profil.split(" - ")[0])
            infos = next(item for item in c_profil_data if item["id"] == cp_id)
            
            historique_chauf = supabase.table('paiements').select('date, montant').eq('chauffeur_id', cp_id).order('date', desc=True).execute().data
            deja_paye = sum(p['montant'] for p in historique_chauf) if historique_chauf else 0.0
            reste = infos['montant_total'] - deja_paye
            progression = int((deja_paye / infos['montant_total']) * 100) if infos['montant_total'] > 0 else 0
            
            statut_badge = "⚪ Nouveau (Aucun paiement)"
            if reste <= 0:
                statut_badge = "🎉 Contrat Terminé"
            elif historique_chauf:
                derniere_date_str = historique_chauf[0]['date']
                derniere_date = datetime.datetime.strptime(derniere_date_str, "%Y-%m-%d").date()
                jours_ecoules = (datetime.date.today() - derniere_date).days
                
                if jours_ecoules <= 7:
                    statut_badge = "🟢 Régulier (À jour)"
                elif jours_ecoules <= 14:
                    statut_badge = f"🟡 À surveiller (Dernier paiement il y a {jours_ecoules} jours)"
                else:
                    statut_badge = f"🔴 Alerte Rouge (Aucun paiement depuis {jours_ecoules} jours)"

            with st.container(border=True):
                colA, colB = st.columns(2)
                colA.subheader(f"👤 {infos['nom']}")
                colA.write(f"📞 Contact : {infos['contact']}")
                if infos['vehicules']:
                    colA.write(f"🏍️ Véhicule : {infos['vehicules']['type']} ({infos['vehicules']['plaque']})")
                else:
                    colA.write("🏍️ Véhicule : Aucun")
                
                colB.subheader("Performance")
                colB.markdown(f"**Statut :** {statut_badge}")
                colB.progress(progression / 100, text=f"Avancement : {progression}%")
                colB.write(f"**Payé :** {deja_paye}$ / **Total :** {infos['montant_total']}$")
                colB.write(f"**Reste à recouvrer :** {reste}$")
            
            st.markdown("#### 📜 Historique personnel des versements")
            if historique_chauf:
                st.dataframe(pd.DataFrame(historique_chauf), hide_index=True, use_container_width=True)
            else:
                st.info("Ce chauffeur n'a encore fait aucun versement.")

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
                
                st.write("---")
                col3, col4, col5 = st.columns(3)
                duree = col3.number_input("Durée estimée (mois)", min_value=1, value=6)
                montant_hebdo = col4.number_input("Versement hebdo prévu ($)", min_value=1.0, value=100.0)
                montant_total = col5.number_input("Somme Totale Fixée ($)*", min_value=1.0, value=2400.0, step=100.0)
                
                if st.form_submit_button("Sauvegarder", use_container_width=True) and nom.strip():
                    v_id = int(vehicule_choisi.split(" - ")[0])
                    supabase.table('chauffeurs').insert({
                        "nom": nom, "contact": contact, "vehicule_id": v_id, 
                        "duree_mois": duree, "montant_total": montant_total, "versement_hebdo": montant_hebdo
                    }).execute()
                    st.success("Chauffeur ajouté ! ✅")
                    st.rerun()

    with tab_edit:
        c_edit_data = supabase.table('chauffeurs').select('id, nom, contact, montant_total').execute().data
        if not c_edit_data: st.info("Aucun chauffeur à modifier.")
        else:
            options_c_edit = [f"{c['id']} - {c['nom']}" for c in c_edit_data]
            c_choisi = st.selectbox("Sélectionner un chauffeur", options_c_edit)
            c_edit_id = int(c_choisi.split(" - ")[0])
            infos_edit = next(item for item in c_edit_data if item["id"] == c_edit_id)
            
            with st.form("form_edit_c"):
                new_nom = st.text_input("Nom", value=infos_edit['nom'])
                new_contact = st.text_input("Téléphone", value=infos_edit['contact'])
                new_total = st.number_input("Corriger le Montant Total ($)", min_value=1.0, value=float(infos_edit['montant_total']))
                
                col_upd, col_del = st.columns(2)
                if col_upd.form_submit_button("💾 Mettre à jour", use_container_width=True):
                    supabase.table('chauffeurs').update({"nom": new_nom, "contact": new_contact, "montant_total": new_total}).eq("id", c_edit_id).execute()
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
        if not v_data: st.info("Votre flotte est vide.")
        else: st.dataframe(pd.DataFrame(v_data), hide_index=True, use_container_width=True)

    with tab_ajout:
        with st.form("form_vehicule", clear_on_submit=True):
            col1, col2 = st.columns(2)
            type_v = col1.selectbox("Type de véhicule", ["Moto", "Voiture", "Tricycle"])
            plaque = col2.text_input("Plaque*")
            moteur = col1.text_input("Moteur*")
            couleur = col2.text_input("Couleur")
            if st.form_submit_button("Enregistrer", use_container_width=True) and plaque.strip() and moteur.strip():
                supabase.table('vehicules').insert({"type": type_v, "plaque": plaque, "moteur": moteur, "couleur": couleur}).execute()
                st.success("Véhicule ajouté ! ✅")
                st.rerun()

    with tab_edit:
        v_edit_data = supabase.table('vehicules').select('id, plaque, type, moteur, couleur').execute().data
        if not v_edit_data: st.info("Aucun véhicule à modifier.")
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
                    supabase.table('vehicules').update({"plaque": new_plaque, "moteur": new_moteur, "couleur": new_couleur}).eq("id", v_edit_id).execute()
                    st.success("Véhicule mis à jour !")
                    st.rerun()
                
                if col_del.form_submit_button("❌ Supprimer le véhicule", use_container_width=True):
                    verif = supabase.table('chauffeurs').select('id').eq('vehicule_id', v_edit_id).execute().data
                    if verif:
                        st.error("⚠️ Impossible : ce véhicule est assigné à un chauffeur !")
                    else:
                        supabase.table('vehicules').delete().eq("id", v_edit_id).execute()
                        st.success("Véhicule supprimé !")
                        st.rerun()
