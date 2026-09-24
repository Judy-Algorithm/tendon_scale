// Keep the existing atlas intact. Personal mode imports only the supplied model adapter.
if(new URLSearchParams(location.search).get('mode')==='personal'){
  await import('./personal.js');
}else{
  await import('./app.js');
}
