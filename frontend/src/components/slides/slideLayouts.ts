import type { Component } from "vue";
import type { SlideLayoutId } from "../../types";
import SlideQuote from "./SlideQuote.vue";
import SlideTextImage from "./SlideTextImage.vue";
import SlideTitleBullets from "./SlideTitleBullets.vue";
import SlideTitleText from "./SlideTitleText.vue";

export const SLIDE_LAYOUTS: Record<
  SlideLayoutId,
  { label: string; component: Component }
> = {
  title_text: { label: "Título + texto", component: SlideTitleText },
  title_bullets: { label: "Título + bullets", component: SlideTitleBullets },
  text_image: { label: "Texto + imagen", component: SlideTextImage },
  quote: { label: "Cita destacada", component: SlideQuote },
};
