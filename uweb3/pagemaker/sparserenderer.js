"use strict"
var uweb_sparserenderer = window.uweb_sparserenderer || {
  verbose: true,
  templatecache: true,
  templates: {},
  HandlePageLoad: function(event){
    if (this.verbose){
      console.log('Attaching event handlers to GET/POST actions for: ', window.location);
    }
    document.querySelectorAll('a').forEach(function(link) {
      if(link.href){
        link.addEventListener('click', this.HandleClickEvent.bind(this));
      }
    }, this);
    document.querySelectorAll('form').forEach(function(link) {
      link.addEventListener('submit', this.HandleSubmitEvent.bind(this));
    }, this);
  },

  HandleHistoryPop: function(event){
    if (this.verbose){
      console.log('History event triggered: ', event.state);
    }
    this.DoClick(event.state);
  },

  HandleClickEvent: function(event){
    if (this.verbose){
      console.log('User Link event registered on: ', event.target.href);
    }
    event.preventDefault();
    if(event.target.href){ // ignore links without
      this.DoClick(event.target.href);
    }
    return false;
  },

  DoClick: async function (path){
    // Fetches the next URL from uweb while telling it we can do the parsing of the template locally.
    let error;
    let response = await fetch(path, {
      headers: {'Accept': 'application/json'}
    })
    .then(response => response.json())
    .then(result => {this.HandleUrlResponse(result, path)})
    .catch((error) => {
      console.error('Error:', error);
    });
  },

  HandleSubmitEvent: function(event){
    if (this.verbose){
      console.log('User Form event registered on: ', event.target.action);
    }
    event.preventDefault();
    if(event.target.action){
      this.DoSubmit(event.target);
    }
    return false;
  },

  DoSubmit: async function (form){
    // Fetches the next URL from uweb while telling it we can do the parsing of the template locally.
    let error;
    const formData = new FormData(form);
    const data = [...formData.entries()];
    console.log(formData, data);
    const PostString = data
      .map(x => `${encodeURIComponent(x[0])}=${encodeURIComponent(x[1])}`)
      .join('&');
    if (this.verbose){
      console.log('User Form submit data: ', PostString);
    }
    if (new Array('head', 'get').indexOf(form.method.toLowerCase()) != -1){
      return this.DoClick(form.action + '?' + PostString);
    }
    let response = await fetch(form.action, {
      method: form.method,
      headers: {'Accept': 'application/json'},
      body: PostString
    })
    .then(response => response.json())
    .then(result => {this.HandleUrlResponse(result, form.action)})
    .catch((error) => {
      console.error('Error:', error);
    });
  },

  HandleUrlResponse: async function (response, path){
    window.history.pushState(path, "", path);
    let template = await this.GetTemplate(response['template'], response['template_hash']);
    Object.keys(response['replacements']).forEach(key => {
        template = template.replaceAll(key, response['replacements'][key]);
      }
    );

    document.body.innerHTML = template;
    // re-init all handlers
    this.HandlePageLoad();
    return template;
  },

  GetTemplate: async function (path, hash){
    let url = '/template/'+hash+path;
    let error;
    if (this.templatecache > 0 &&
        this.templates[path]){
      if (this.verbose){
        console.log('Cached template hit for '+path+' Saved '+this.templates[path].length+' bytes');
      }
      return this.templates[path];
    }
    return fetch(url)//,
      //{integrity: "sha256-"+hash})
    .then(response => response.text())
    .then(data => {
      this.templates[path] = data;
      return data;
    })
    .catch((error) => {
      console.error('Error:', error);
    });
  },

  Load: function(){
    window.addEventListener('load', this.HandlePageLoad.bind(this));
    window.addEventListener('popstate', this.HandleHistoryPop.bind(this));
  }


}.Load();
