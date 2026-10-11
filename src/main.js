import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import { createVuetify } from 'vuetify';
import { VApp,VAppBar,VAppBarNavIcon,VAvatar,VBtn,VIcon,VSpacer,VMain,VNavigationDrawer,VList,VListItem } from 'vuetify/components';
import { Ripple } from 'vuetify/directives';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';
import App from './App.vue';
import Home from './views/Home.vue';
import Module from './views/Module.vue';
import './style.css';
const router=createRouter({history:createWebHistory(),scrollBehavior(to,from,saved){return saved||{top:0}},routes:[
 {path:'/',component:Home},
 {path:'/:module(rank)/:tab(Code)',component:Module},
 {path:'/:module(introduction|chemical|wpn|rank)/:tab(Description|Data|Figure)?',component:Module},
 {path:'/ww/:tab(Description|Data|Figure)?',redirect:to=>({path:'/wpn/'+(to.params.tab||'Data')})},
 {path:'/imputation/:tab(Description|Data|Figure)?',redirect:to=>({path:'/introduction/'+(to.params.tab==='Description'?'Description':'Data'),query:{view:'validation'}})},
 {path:'/:pathMatch(.*)*',redirect:'/'}
]});
router.beforeEach(to=>{if(to.params.module&&!to.params.tab)return {path:`/${to.params.module}/${to.params.module === 'wpn' ? 'Data' : to.params.module === 'rank' ? 'Figure' : 'Description'}`,query:to.query}});
router.afterEach(to=>{document.title=to.params.module?`WPN · ${{introduction:'Introduction',chemical:'Chemical',wpn:'WPN',rank:'Rank'}[to.params.module]} · ${to.params.tab||'Data'}`:'WPN · Wastewater-based model platform'});
createApp(App).use(router).use(createVuetify({components:{VApp,VAppBar,VAppBarNavIcon,VAvatar,VBtn,VIcon,VSpacer,VMain,VNavigationDrawer,VList,VListItem},directives:{Ripple}})).mount('#app');
