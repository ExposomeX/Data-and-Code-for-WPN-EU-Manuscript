<template>
 <v-app :class="{'table-data-page':['chemical','rank'].includes($route.params.module)&&$route.params.tab==='Data'}">
  <v-app-bar app class="site-header">
   <v-app-bar-nav-icon class="mobile-toggle" aria-label="Open navigation" @click="mobileMenu=!mobileMenu" />
   <a href="https://www.exposomex.cn/" class="home-brand" aria-label="ExposomeX homepage"><img class="brand-logo" src="/exposomex-logo.png" alt="ExposomeX logo" /><span class="brand-name">ExposomeX</span></a>
   <v-spacer />
   <nav class="desktop-navigation" aria-label="Main navigation"><v-btn class="home-navigation-link" to="/" icon="mdi-home-outline" size="large" title="Home" aria-label="Home" :active="$route.path==='/'" active-color="primary" /><v-btn v-for="s in sections" :key="s.slug" size="large" :to="s.path" :active="$route.params.module===s.slug" active-color="primary">{{s.label}}</v-btn></nav>
  </v-app-bar>
  <v-navigation-drawer v-model="mobileMenu" temporary><v-list><v-list-item to="/" title="Home" @click="mobileMenu=false" /><v-list-item v-for="s in sections" :key="s.slug" :title="s.label" :to="s.path" @click="mobileMenu=false" /></v-list></v-navigation-drawer>
  <v-main><router-view /></v-main>
  <footer v-if="$route.path!=='/'" class="site-footer">WPN <span aria-hidden="true">·</span> {{paper.longName}}</footer>
 </v-app>
</template>
<script setup>
import {ref} from 'vue';
import paper from './content/paper.json';
const mobileMenu=ref(false);
const sections=[{slug:'introduction',label:'Introduction',path:'/introduction/Description'},{slug:'chemical',label:'Chemical',path:'/chemical/Description'},{slug:'wpn',label:'WPN',path:'/wpn/Data'},{slug:'rank',label:'Rank',path:'/rank/Figure?source=current'}];
</script>
<style scoped>
.desktop-navigation .home-navigation-link{width:44px;min-width:44px;height:44px;align-self:center;margin-right:4px}
</style>
