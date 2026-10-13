// Native fields remain editable; provider and key ownership are policy-owned.
let active=false,observer=null;
function decorate(){
    if(active)for(const label of document.querySelectorAll('.model-switcher-model-value span[x-text$=".provider"]')){
        if(label.textContent==='requesty_guarded')label.textContent='Requesty (A0 Privacy)';
    }
    for(const select of document.querySelectorAll('select[x-model="model.provider"]')){
        const root=select.closest('[x-data]');
        if(!root)continue;
        const requesty=select.value==='requesty_guarded';
        if(active&&requesty){
            if(!select.hasAttribute('data-privacy-provider')){
                select.dataset.privacyProvider=String(select.disabled);select.disabled=true;
                select.addEventListener('change',decorate);
            }
            let note=root.querySelector('.privacy-preset-key-source');
            if(!note){note=document.createElement('p');note.className='privacy-preset-key-source';note.textContent='Requesty ist durch Privacy Agent festgelegt. Schlüssel: zentral eingerichtet; ein eigener Profilschlüssel hat Vorrang. Modelle hier wie gewohnt auswählen, auch bei aktivem Schutz. Für eine anbieterspezifische Modell-ID mit einem Anbieterpräfix und / suchen.';root.append(note);}
            for(const key of [...root.querySelectorAll('input')].filter(input=>input.type==='password'||input.getAttribute(':value')?.includes('apiKeyValues'))){
                if(!key.hasAttribute('data-privacy-key'))key.dataset.privacyKey=String(key.disabled);
                key.disabled=true;
            }
        }else if(select.hasAttribute('data-privacy-provider')){
            select.disabled=select.dataset.privacyProvider==='true';delete select.dataset.privacyProvider;
            root.querySelector('.privacy-preset-key-source')?.remove();
            for(const key of root.querySelectorAll('input[data-privacy-key]')){key.disabled=key.dataset.privacyKey==='true';delete key.dataset.privacyKey;}
        }
    }
}
export function updateNativePresetUI(enabled){
    active=!!enabled;
    if(!observer){observer=new MutationObserver(decorate);observer.observe(document.body,{childList:true,subtree:true});document.addEventListener('change',decorate);}
    decorate();
}
