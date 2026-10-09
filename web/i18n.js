// Diccionarios ES/EN. t(key) resuelve según localStorage('strata_lang').
const I18N = {
  es: {
    nav_operate: "Operar", nav_observe: "Observar", nav_connect: "Conectar", nav_system: "Sistema", crumb: "Conector Strata ↔ agentes", active_short: "ACTIVO",
    tab_models: "Modelos", tab_perf: "Rendimiento", tab_traces: "Trazabilidad", tab_connection: "Conexión", tab_params: "Parámetros",
    trace_title: "Trazabilidad de requests", trace_refresh: "actualizar", trace_empty: "Todavía no hay requests observados.",
    trace_detail: "Detalle de ejecución", trace_select: "Selecciona una request para ver pensamiento, respuesta y métricas.",
    trace_reasoning: "Razonamiento expuesto por el modelo", trace_response: "Respuesta", trace_errors: "Errores y diagnóstico", trace_prompt: "Prompt del usuario", trace_tools: "Herramientas", trace_usage: "Uso y tiempo",
    trace_running: "ejecutando", trace_completed: "completada", trace_error: "error",
    conn_title: "Conexión y exposición", conn_refresh: "actualizar", conn_mode_label: "Modo de escucha", conn_local: "Solo este PC", conn_lan: "Red local", conn_cors: "Permitir CORS para clientes web", conn_apply: "guardar y preparar cambio", conn_security: "La API local no se expone por defecto. Al abrirla en red, los clientes remotos deben usar el token Bearer.", conn_urls: "Cómo conectar otro PC",
    tab_prefs: "Preferencias", prefs_title: "Preferencias de uso", prefs_reset: "restaurar", prefs_theme: "Tema visual", prefs_density: "Densidad de datos", prefs_motion: "Reducir animaciones", prefs_reasoning: "Mostrar razonamiento en trazas", prefs_saved: "Preferencias guardadas", prefs_reset_done: "Preferencias restauradas", prefs_help: "Estas preferencias se guardan solo en este navegador. No cambian Strata ni consumen recursos del modelo.", pref_dark: "Oscuro", pref_ink: "Índigo", pref_light: "Claro", pref_compact: "Compacta", pref_comfort: "Cómoda", quick_help_title: "Qué hace cada sección",
    help_models: "Cambia el modelo activo y controla su estado.", help_perf: "Compara velocidad, VRAM y rendimiento histórico.", help_traces: "Sigue prompt, razonamiento, respuesta y errores.", help_connection: "Controla localhost, LAN, CORS y autenticación.", help_prefs: "Personaliza aspecto, densidad y visibilidad.", help_params: "Edita sampling y flags del engine.", help_opt: "Busca una configuración adecuada para tu contexto.", help_update: "Comprueba versiones y actualizaciones del engine.", help_tunnel: "Expone la API mediante un túnel cifrado temporal.", help_add: "Registra un modelo y valida si cabe en el PC.", help_log: "Consulta la actividad local de la consola.",
    conn_local_status: "Solo local", conn_lan_status: "Red local activa", conn_restart: "requiere reinicio del servicio",
    tab_update: "Actualización", tab_tunnel: "Túnel", tab_add: "Alta", tab_log: "Actividad",
    g_vram: "VRAM usada", g_ram: "RAM del sistema", g_gpu: "uso de GPU",
    active_model: "MODELO ACTIVO",
    inv_title: "Inventario de modelos", inv_hint: "una instancia a la vez · la 3090 no admite dos cargados",
    c_model: "modelo", c_state: "estado", c_port: "puerto", c_toks: "tok/s", c_ctx: "contexto",
    c_kv: "KV", c_vramfree: "VRAM libre", c_eng: "engine", c_acts: "acciones",
    c_time: "hora", c_dur: "dur", c_prompt: "prompt", c_out: "salida", c_hit: "hit cache", c_mtp: "drafts MTP",
    detail: "Detalle", close: "cerrar", last_req: "Últimos requests",
    live_title: "Métricas en vivo", hist_title: "Tendencia histórica por modelo",
    hist_hint: "tok/s y VRAM libre muestreados cada 60 s",
    cmp_title: "Rendimiento por configuración", cmp_hint: "compara setups distintos del mismo modelo",
    c_setup: "setup", c_samples: "muestras", c_tokavg: "tok/s prom.", c_pre: "prefill prom.",
    params_title: "Parámetros", save: "guardar", restart_apply: "reiniciar para aplicar",
    params_note: "cada campo tiene su explicación al pasar el mouse. Los que dicen «requiere reinicio» se aplican al volver a cargar el modelo.",
    upd_title: "Strata: versión y actualización", upd_check: "verificar ahora", upd_apply: "actualizar Strata",
    tun_title: "Túnel cifrado (cloudflared)", tun_start: "activar túnel", tun_stop: "apagar túnel",
    tun_note: "Túnel quick de Cloudflare: gratuito, TLS cifrado de extremo a extremo, sin abrir puertos. Al activarlo se exige API key en los modelos; sin esa key el túnel no se levanta. La URL cambia en cada sesión.",
    add_title: "Alta de modelo en el catálogo", fit_btn: "verificar si cabe en el PC",
    f_gguf: "ruta del GGUF (shard 1)|/home/user/.../modelo-00001-of-00002.gguf",
    f_id: "id|se deriva del archivo", f_label: "etiqueta|opcional", f_port: "puerto|auto",
    f_pack: "pack Strata|si falta, se crea junto al modelo", f_prof: "expert profile (opcional)|data/expert-profile.bin",
    add_btn: "agregar al catálogo", fit_ctx_lbl: "contexto / KV",
    add_note: "Requisito: Strata no carga un GGUF suelto — necesita su pack (index.txt, dense.bin, tokenizer/). Crearlo desde el repo: python tools/iq_pack.py --gguf <shard1> --out <pack> --base <pack existente> (con --base reutiliza dense.bin por hardlink y ahorra ~1,5 GB).",
    log_title: "Actividad de la consola", clear: "limpiar",
    a_use: "usar", a_params: "parámetros", a_unload: "descargar", a_stop: "detener", a_remove: "quitar",
    st_active: "ACTIVO", st_running: "corriendo", st_stopped: "detenido",
    upd_available: "hay actualización", upd_current: "al día",
    tun_on: "túnel activo", tun_off: "túnel apagado",
    tab_opt: "Optimizador", opt_title: "Optimizador de configuración",
    ov_eyebrow: "PLANO DE CONTROL · LOCAL", ov_title: "Orquestación de modelos",
    ov_subtitle: "Un punto de control para Strata, Hermes y tus agentes.", ov_refresh: "actualizar estado",
    ov_optimize: "optimizar contexto", ov_params: "editar parámetros", ov_active: "MODELO ACTIVO",
    ov_context: "CONTEXTO", ov_load: "CARGA GPU", ov_catalog: "CATÁLOGO", ov_catalog_sub: "modelos registrados",
    opt_bal: "equilibrado", opt_speed: "velocidad", opt_long: "contexto largo", opt_code: "código",
    opt_run: "buscar mejor config",
    opt_hint: "elegí el contexto objetivo y el perfil; el sistema busca la mejor combinación de KV, crecimiento, MTP y lookup según la VRAM/RAM reales y la historia de rendimiento.",
    opt_reco: "Recomendada", opt_alt: "Alternativas", opt_apply: "aplicar al modelo", eval_title:"Evaluación medida", eval_hint:"Bloquea la inferencia durante las mediciones.", eval_runs:"ejecuciones por prompt", eval_long:"caracteres del prompt largo", eval_run:"evaluar candidatos", eval_apply:"aplicar configuración medida", eval_details:"ver métricas", eval_empty:"Todavía no hay resultados de evaluación.",
    opt_hist: "Referencia histórica", opt_est: "Estimación",
  },
  en: {
    nav_operate: "Operate", nav_observe: "Observe", nav_connect: "Connect", nav_system: "System", crumb: "Strata connector ↔ agents", active_short: "ACTIVE",
    tab_models: "Models", tab_perf: "Performance", tab_traces: "Trace", tab_connection: "Connection", tab_params: "Parameters",
    trace_title: "Request trace", trace_refresh: "refresh", trace_empty: "No observed requests yet.",
    trace_detail: "Execution detail", trace_select: "Select a request to inspect reasoning, response and metrics.",
    trace_reasoning: "Reasoning exposed by the model", trace_response: "Response", trace_errors: "Errors and diagnostics", trace_prompt: "User prompt", trace_tools: "Tools", trace_usage: "Usage and timing",
    trace_running: "running", trace_completed: "completed", trace_error: "error",
    conn_title: "Connection and exposure", conn_refresh: "refresh", conn_mode_label: "Listen mode", conn_local: "This PC only", conn_lan: "Local network", conn_cors: "Allow CORS for web clients", conn_apply: "save and prepare change", conn_security: "The API is local-only by default. When opened on the network, remote clients must use the Bearer token.", conn_urls: "Connect another PC",
    tab_prefs: "Preferences", prefs_title: "Usage preferences", prefs_reset: "restore", prefs_theme: "Visual theme", prefs_density: "Data density", prefs_motion: "Reduce motion", prefs_reasoning: "Show reasoning in traces", prefs_saved: "Preferences saved", prefs_reset_done: "Preferences restored", prefs_help: "These preferences are saved only in this browser. They do not change Strata or consume model resources.", pref_dark: "Dark", pref_ink: "Indigo", pref_light: "Light", pref_compact: "Compact", pref_comfort: "Comfortable", quick_help_title: "What each section does",
    help_models: "Switch the active model and control its state.", help_perf: "Compare speed, VRAM and historical performance.", help_traces: "Follow prompt, reasoning, response and errors.", help_connection: "Control localhost, LAN, CORS and authentication.", help_prefs: "Customize appearance, density and visibility.", help_params: "Edit sampling and engine flags.", help_opt: "Find a configuration for your target context.", help_update: "Check engine versions and updates.", help_tunnel: "Expose the API through a temporary encrypted tunnel.", help_add: "Register a model and check whether it fits the PC.", help_log: "Review local console activity.",
    conn_local_status: "Local only", conn_lan_status: "Local network active", conn_restart: "service restart required",
    tab_update: "Update", tab_tunnel: "Tunnel", tab_add: "Register", tab_log: "Activity",
    g_vram: "VRAM used", g_ram: "system RAM", g_gpu: "GPU utilization",
    active_model: "ACTIVE MODEL",
    inv_title: "Model inventory", inv_hint: "one instance at a time · the 3090 cannot hold two",
    c_model: "model", c_state: "state", c_port: "port", c_toks: "tok/s", c_ctx: "context",
    c_kv: "KV", c_vramfree: "free VRAM", c_eng: "engine", c_acts: "actions",
    c_time: "time", c_dur: "dur", c_prompt: "prompt", c_out: "output", c_hit: "cache hit", c_mtp: "MTP drafts",
    detail: "Detail", close: "close", last_req: "Recent requests",
    live_title: "Live metrics", hist_title: "Historical trend per model",
    hist_hint: "tok/s and free VRAM sampled every 60 s",
    cmp_title: "Performance by configuration", cmp_hint: "compare different setups of the same model",
    c_setup: "setup", c_samples: "samples", c_tokavg: "avg tok/s", c_pre: "avg prefill",
    params_title: "Parameters", save: "save", restart_apply: "restart to apply",
    params_note: "hover each field for its explanation. Fields marked «restart» apply when the model reloads.",
    upd_title: "Strata: version and update", upd_check: "check now", upd_apply: "update Strata",
    tun_title: "Encrypted tunnel (cloudflared)", tun_start: "start tunnel", tun_stop: "stop tunnel",
    tun_note: "Cloudflare quick tunnel: free, end-to-end TLS, no open ports. Starting it forces an API key on the models; without a key the tunnel refuses to start. The URL changes each session.",
    add_title: "Register a model in the catalog", fit_btn: "check if it fits this PC",
    f_gguf: "GGUF path (shard 1)|/home/.../model-00001-of-00002.gguf",
    f_id: "id|derived from file", f_label: "label|optional", f_port: "port|auto",
    f_pack: "Strata pack|created next to the model if missing", f_prof: "expert profile (optional)|data/expert-profile.bin",
    add_btn: "add to catalog", fit_ctx_lbl: "context / KV",
    add_note: "Requirement: Strata will not load a bare GGUF — it needs its pack (index.txt, dense.bin, tokenizer/). Build it from the repo: python tools/iq_pack.py --gguf <shard1> --out <pack> --base <existing pack> (--base hardlinks dense.bin, saving ~1.5 GB).",
    log_title: "Console activity", clear: "clear",
    a_use: "use", a_params: "params", a_unload: "unload", a_stop: "stop", a_remove: "remove",
    st_active: "ACTIVE", st_running: "running", st_stopped: "stopped",
    upd_available: "update available", upd_current: "up to date",
    tun_on: "tunnel on", tun_off: "tunnel off",
    tab_opt: "Optimizer", opt_title: "Configuration optimizer",
    ov_eyebrow: "CONTROL PLANE · LOCAL", ov_title: "Model orchestration",
    ov_subtitle: "One control point for Strata, Hermes and your agents.", ov_refresh: "refresh state",
    ov_optimize: "optimize context", ov_params: "edit parameters", ov_active: "ACTIVE MODEL",
    ov_context: "CONTEXT", ov_load: "GPU LOAD", ov_catalog: "CATALOG", ov_catalog_sub: "registered models",
    opt_bal: "balanced", opt_speed: "speed", opt_long: "long context", opt_code: "code",
    opt_run: "find best config",
    opt_hint: "set the target context and profile; the system searches the best KV / growth / MTP / lookup mix using real VRAM/RAM and past performance.",
    opt_reco: "Recommended", opt_alt: "Alternatives", opt_apply: "apply to model", eval_title:"Measured evaluation", eval_hint:"Inference is blocked while candidates are measured.", eval_runs:"runs per prompt", eval_long:"long prompt characters", eval_run:"evaluate candidates", eval_apply:"apply measured configuration", eval_details:"view metrics", eval_empty:"No evaluation results yet.",
    opt_hist: "History reference", opt_est: "Estimate",
  },
  pt: {}, fr: {}, de: {}
};
const RUNTIME_I18N = {
  en: {
    status_error:'Status: {error}', token_required:'Connection requires the console token.', performance_error:'Performance: {error}', connection_error:'Connection: {error}', trace_error_prefix:'Traces: {error}', params_error:'Parameters: {error}', update_error:'Update: {error}', tunnel_error:'Tunnel: {error}', fit_error:'Fit check: {error}', remote_auth:'Bearer authentication', local_no_auth:'local access without token', update_finished:'Update completed; review the result.', upd_install:'Install Strata', upd_missing:'Strata is not installed; the installer will clone the official repository.', upd_ready:'Strata source is installed; model setup is still required.', upd_changes:'Changes available from upstream', updates_available:'{count} updates available', engine_setup_required:'Strata setup required', update_engine:'engine', update_console:'console', tunnel_started:'Tunnel: {status}', tunnel_stopped:'Tunnel stopped.', model_added:'Model added: {model}', model_switching:'Switching to {model}; loading may take several minutes', model_active:'Active model: {model}', model_removed:'Removed from catalog: {model}', model_unloaded:'Unloaded: {model}', model_stopped:'Stopped: {model}', select_model_first:'Select a model first', config_saved:'Configuration saved; restart required: {file}', optimizer_no_fit:'No viable combination with the current memory.', optimizer_error:'Optimizer: {error}', no_highlighted_risks:'no highlighted risks', evaluation_prepare:'Evaluation is blocking inference and preparing candidates…', evaluation_complete:'Evaluation complete: {count} candidates measured.', evaluation_error:'Evaluation: {error}', measured_applied:'Measured configuration applied to {model}; restart completed', engine_local:'local engine', commit_local:'local commit', commit_remote:'remote commit', behind:'behind', status:'status', local_changes_preserved:'Local changes detected; the update preserves them through stash/merge.', update_readonly:'The check does not modify code.', configured:'configured', yes:'yes', no:'no', state:'state', url:'URL', api_key_configured:'API key configured', tunnel:'Tunnel: {status}', tunnel_stopped:'Tunnel stopped', model_added:'Model added: {model}', token_saved_log:'Token saved locally', select_model_eval:'Select a model before evaluating', performance_decode:'decode', performance_avg:'average', performance_prefill:'prefill', performance_free_vram:'free VRAM', performance_expert_cache:'expert cache', performance_queue:'queue', no_history:'no historical samples yet', trace_model:'model', trace_duration:'duration', trace_tokens:'tokens', trace_finish:'finish', trace_hidden:'Hidden by local preference.', trace_unavailable:'The model did not expose reasoning for this request.', trace_no_model:'No model selected', trace_no_fit:'No viable fit', fit_key:'fit', expert_budget:'expert budget', evidence:'Evidence', remove_preserves_files:'Model files and packs will not be deleted.', api_local:'Local API', api_other_pc:'API from another PC', panel:'Panel', header:'Header', lan_not_exposed:'Enable Local network to obtain a network URL.', not_exposed:'not exposed', evaluation_score:'score', evaluation_short:'short', evaluation_long:'long', evaluation_p95:'long p95', evaluation_success:'success', state_failed:'failed', job_failed:'job failed', job_cancelled:'job cancelled', job_timeout:'job timeout'
  },
  es: {
    token_saved:'Token guardado', model_switching:'Cambiando a {model}; la carga puede tardar varios minutos', model_active:'Modelo activo: {model}', model_removed:'Modelo quitado del catálogo: {model}', model_unloaded:'Modelo descargado: {model}', model_stopped:'Modelo detenido: {model}', select_model_first:'Selecciona un modelo primero', config_saved:'Configuración guardada; requiere reinicio: {file}', optimizer_no_fit:'No hay combinación viable con la memoria actual.', optimizer_error:'Optimizador: {error}', no_highlighted_risks:'sin riesgos destacados', evaluation_prepare:'La evaluación bloquea la inferencia y prepara candidatos…', evaluation_complete:'Evaluación completa: {count} candidatos medidos.', evaluation_error:'Evaluación: {error}', measured_applied:'Configuración medida aplicada a {model}; reinicio completado', engine_local:'engine local', commit_local:'commit local', commit_remote:'commit remoto', behind:'atrás', status:'estado', local_changes_preserved:'Hay cambios locales; la actualización los conserva mediante stash/merge.', update_readonly:'La verificación no modifica el código.', configured:'configurada', yes:'sí', no:'no', state:'estado', url:'URL', api_key_configured:'API key configurada', tunnel:'túnel: {status}', tunnel_stopped:'túnel apagado', model_added:'Modelo agregado: {model}', token_saved_log:'Token guardado localmente', select_model_eval:'Selecciona un modelo antes de evaluar', performance_decode:'decode', performance_avg:'promedio', performance_prefill:'prefill', performance_free_vram:'VRAM libre', performance_expert_cache:'cache de expertos', performance_queue:'cola', no_history:'sin muestras todavía', trace_model:'modelo', trace_duration:'duración', trace_tokens:'tokens', trace_finish:'finish', trace_hidden:'Oculto por preferencia local.', trace_unavailable:'El modelo no expuso razonamiento en esta request.', no_fit:'No hay combinación viable', evaluation_score:'score', evaluation_short:'corto', evaluation_long:'largo', evaluation_p95:'p95 largo', evaluation_success:'éxito'
  },
  pt: { token_saved:'Token salvo', select_model_first:'Selecione um modelo primeiro', optimizer_no_fit:'Nenhuma combinação viável com a memória atual.', no_highlighted_risks:'sem riscos destacados', evaluation_prepare:'A avaliação bloqueia a inferência e prepara candidatos…', evaluation_complete:'Avaliação concluída: {count} candidatos medidos.', evaluation_error:'Avaliação: {error}', yes:'sim', no:'não' },
  fr: { token_saved:'Jeton enregistré', select_model_first:'Sélectionnez d’abord un modèle', optimizer_no_fit:'Aucune combinaison viable avec la mémoire actuelle.', no_highlighted_risks:'aucun risque notable', evaluation_prepare:'L’évaluation bloque l’inférence et prépare les candidats…', evaluation_complete:'Évaluation terminée : {count} candidats mesurés.', evaluation_error:'Évaluation : {error}', yes:'oui', no:'non' },
  de: { token_saved:'Token gespeichert', select_model_first:'Zuerst ein Modell auswählen', optimizer_no_fit:'Keine geeignete Kombination mit dem aktuellen Speicher.', no_highlighted_risks:'keine hervorgehobenen Risiken', evaluation_prepare:'Die Bewertung blockiert die Inferenz und bereitet Kandidaten vor…', evaluation_complete:'Bewertung abgeschlossen: {count} Kandidaten gemessen.', evaluation_error:'Bewertung: {error}', yes:'ja', no:'nein' }
};
Object.entries(RUNTIME_I18N).forEach(([locale, values]) => Object.assign(I18N[locale], values));
I18N.pt = Object.assign({}, I18N.en, {
  tab_models:'Modelos',tab_perf:'Desempenho',tab_traces:'Rastreamento',tab_connection:'Conexão',tab_params:'Parâmetros',tab_update:'Atualização',tab_tunnel:'Túnel',tab_add:'Cadastro',tab_log:'Atividade',
  trace_title:'Rastreamento de requisições',trace_refresh:'atualizar',trace_empty:'Nenhuma requisição observada.',trace_detail:'Detalhes da execução',trace_select:'Selecione uma requisição para ver raciocínio, resposta e métricas.',trace_reasoning:'Raciocínio exposto pelo modelo',trace_response:'Resposta',trace_errors:'Erros e diagnóstico',trace_prompt:'Prompt do usuário',trace_tools:'Ferramentas',trace_usage:'Uso e tempo',trace_running:'executando',trace_completed:'concluída',trace_error:'erro',
  conn_title:'Conexão e exposição',conn_refresh:'atualizar',conn_mode_label:'Modo de escuta',conn_local:'Somente este PC',conn_lan:'Rede local',conn_cors:'Permitir CORS para clientes web',conn_apply:'salvar e preparar mudança',conn_security:'A API é local por padrão. Ao abrir na rede, clientes remotos devem usar o token Bearer.',conn_urls:'Como conectar outro PC',conn_local_status:'Somente local',conn_lan_status:'Rede local ativa',conn_restart:'reinicialização do serviço necessária',
  ov_title:'Orquestração de modelos',ov_subtitle:'Um ponto de controle para Strata, Hermes e seus agentes.',ov_refresh:'atualizar estado',ov_optimize:'otimizar contexto',ov_params:'editar parâmetros',ov_active:'MODELO ATIVO',ov_context:'CONTEXTO',ov_load:'CARGA DA GPU',ov_catalog:'CATÁLOGO',ov_catalog_sub:'modelos registrados',
  inv_title:'Inventário de modelos',params_title:'Parâmetros',save:'salvar',restart_apply:'reiniciar para aplicar',live_title:'Métricas ao vivo',hist_title:'Tendência histórica por modelo',upd_title:'Strata: versão e atualização',tun_title:'Túnel criptografado',add_title:'Cadastrar modelo',log_title:'Atividade do console',clear:'limpar',a_use:'usar',a_params:'parâmetros',a_unload:'descarregar',a_stop:'parar',st_active:'ATIVO',st_running:'executando',st_stopped:'parado',tab_opt:'Otimizador',opt_title:'Otimizador de configuração',opt_run:'buscar melhor configuração',opt_reco:'Recomendada',opt_alt:'Alternativas',opt_apply:'aplicar ao modelo', eval_title:'Avaliação medida', eval_hint:'A inferência é bloqueada durante as medições.', eval_runs:'execuções por prompt', eval_long:'caracteres do prompt longo', eval_run:'avaliar candidatos', eval_apply:'aplicar configuração medida', eval_details:'ver métricas', eval_empty:'Ainda não há resultados.'
});
I18N.fr = Object.assign({}, I18N.en, {
  tab_models:'Modèles',tab_perf:'Performances',tab_traces:'Traçabilité',tab_connection:'Connexion',tab_params:'Paramètres',tab_update:'Mise à jour',tab_tunnel:'Tunnel',tab_add:'Ajouter',tab_log:'Activité',
  trace_title:'Traçabilité des requêtes',trace_refresh:'actualiser',trace_empty:'Aucune requête observée.',trace_detail:"Détails d'exécution",trace_select:'Sélectionnez une requête pour voir le raisonnement, la réponse et les métriques.',trace_reasoning:'Raisonnement exposé par le modèle',trace_response:'Réponse',trace_errors:'Erreurs et diagnostic',trace_prompt:'Prompt utilisateur',trace_tools:'Outils',trace_usage:'Utilisation et durée',trace_running:'en cours',trace_completed:'terminée',trace_error:'erreur',
  conn_title:'Connexion et exposition',conn_refresh:'actualiser',conn_mode_label:"Mode d'écoute",conn_local:'Ce PC uniquement',conn_lan:'Réseau local',conn_cors:'Autoriser CORS pour les clients web',conn_apply:'enregistrer et préparer',conn_security:"L'API est locale par défaut. Sur le réseau, les clients distants doivent utiliser le token Bearer.",conn_urls:'Connecter un autre PC',conn_local_status:'Local uniquement',conn_lan_status:'Réseau local actif',conn_restart:'redémarrage du service requis',
  ov_title:'Orchestration des modèles',ov_subtitle:'Un point de contrôle pour Strata, Hermes et vos agents.',ov_refresh:"actualiser l'état",ov_optimize:'optimiser le contexte',ov_params:'modifier les paramètres',ov_active:'MODÈLE ACTIF',ov_context:'CONTEXTE',ov_load:'CHARGE GPU',ov_catalog:'CATALOGUE',ov_catalog_sub:'modèles enregistrés',
  inv_title:'Inventaire des modèles',params_title:'Paramètres',save:'enregistrer',restart_apply:'redémarrer pour appliquer',live_title:'Métriques en direct',hist_title:'Tendance historique par modèle',upd_title:'Strata : version et mise à jour',tun_title:'Tunnel chiffré',add_title:'Ajouter un modèle',log_title:'Activité de la console',clear:'effacer',a_use:'utiliser',a_params:'paramètres',a_unload:'décharger',a_stop:'arrêter',st_active:'ACTIF',st_running:'en cours',st_stopped:'arrêté',tab_opt:'Optimiseur',opt_title:'Optimiseur de configuration',opt_run:'trouver la meilleure configuration',opt_reco:'Recommandée',opt_alt:'Alternatives',opt_apply:'appliquer au modèle'
});
I18N.de = Object.assign({}, I18N.en, {
  tab_models:'Modelle',tab_perf:'Leistung',tab_traces:'Nachverfolgung',tab_connection:'Verbindung',tab_params:'Parameter',tab_update:'Update',tab_tunnel:'Tunnel',tab_add:'Hinzufügen',tab_log:'Aktivität',
  trace_title:'Anfrage-Nachverfolgung',trace_refresh:'aktualisieren',trace_empty:'Noch keine Anfragen beobachtet.',trace_detail:'Ausführungsdetails',trace_select:'Anfrage auswählen, um Denken, Antwort und Metriken zu sehen.',trace_reasoning:'Vom Modell ausgegebenes Denken',trace_response:'Antwort',trace_errors:'Fehler und Diagnose',trace_prompt:'Benutzer-Prompt',trace_tools:'Werkzeuge',trace_usage:'Verbrauch und Zeit',trace_running:'läuft',trace_completed:'abgeschlossen',trace_error:'Fehler',
  conn_title:'Verbindung und Freigabe',conn_refresh:'aktualisieren',conn_mode_label:'Listener-Modus',conn_local:'Nur dieser PC',conn_lan:'Lokales Netzwerk',conn_cors:'CORS für Web-Clients erlauben',conn_apply:'speichern und Änderung vorbereiten',conn_security:'Die API ist standardmäßig nur lokal. Im Netzwerk müssen entfernte Clients das Bearer-Token verwenden.',conn_urls:'Anderen PC verbinden',conn_local_status:'Nur lokal',conn_lan_status:'Lokales Netzwerk aktiv',conn_restart:'Dienstneustart erforderlich',
  ov_title:'Modell-Orchestrierung',ov_subtitle:'Eine Steuerzentrale für Strata, Hermes und deine Agenten.',ov_refresh:'Status aktualisieren',ov_optimize:'Kontext optimieren',ov_params:'Parameter bearbeiten',ov_active:'AKTIVES MODELL',ov_context:'KONTEXT',ov_load:'GPU-LAST',ov_catalog:'KATALOG',ov_catalog_sub:'registrierte Modelle',
  inv_title:'Modellinventar',params_title:'Parameter',save:'speichern',restart_apply:'zum Anwenden neu starten',live_title:'Live-Metriken',hist_title:'Historischer Trend pro Modell',upd_title:'Strata: Version und Update',tun_title:'Verschlüsselter Tunnel',add_title:'Modell registrieren',log_title:'Konsolenaktivität',clear:'löschen',a_use:'verwenden',a_params:'Parameter',a_unload:'entladen',a_stop:'stoppen',st_active:'AKTIV',st_running:'läuft',st_stopped:'gestoppt',tab_opt:'Optimierer',opt_title:'Konfigurationsoptimierer',opt_run:'beste Konfiguration suchen',opt_reco:'Empfohlen',opt_alt:'Alternativen',opt_apply:'auf Modell anwenden'
});
Object.entries(RUNTIME_I18N).forEach(([locale, values]) => Object.assign(I18N[locale], values));
function lang() { return localStorage.getItem('strata_lang') || 'en'; }
function t(k) { return (I18N[lang()] || I18N.en)[k] || I18N.en[k] || k; }
function applyLang() {
  document.querySelectorAll('[data-t]').forEach(el => {
    const v = t(el.dataset.t);
    if (el.tagName === 'LABEL' && v.includes('|')) {
      const [txt, ph] = v.split('|');
      el.childNodes[0] && el.childNodes[0].nodeType === 3
        ? el.childNodes[0].textContent = txt
        : el.insertBefore(document.createTextNode(txt), el.firstChild);
      const inp = el.querySelector('input'); if (inp && ph) inp.placeholder = ph;
    } else if (!el.children.length) {
      el.textContent = v;
    }
  });
  document.documentElement.lang = lang();
}
