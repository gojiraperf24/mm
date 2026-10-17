// Editable prototype enclosure. Measure your ESP32 board before printing.
// Board mounting uses foam/Velcro; no invented board-hole dimensions.
$fn=48;
inside_length=60;
inside_width=32;
inside_height=22;
wall=2.4;
strap_width=20;
part="base"; // "base", "lid" or "both"

module base(){
  difference(){
    cube([inside_length+2*wall,inside_width+2*wall,inside_height+wall]);
    translate([wall,wall,wall]) cube([inside_length,inside_width,inside_height+1]);
    // USB and detachable glove harness openings; confirm placement on your board.
    translate([-1,10,5]) cube([wall+2,16,10]);
    translate([inside_length+wall,10,5]) cube([wall+2,16,12]);
    // Side ventilation; no battery cell inside the first USB-powered prototype.
    for(x=[12:8:48]) translate([x,-1,12]) cube([3,wall+2,5]);
  }
  for(y=[-7,inside_width+2*wall]){
    difference(){
      translate([15,y,0]) cube([strap_width+8,7,wall]);
      translate([19,y+2,-1]) cube([strap_width,3,wall+2]);
    }
  }
}
module lid(){
  difference(){
    union(){
      cube([inside_length+2*wall,inside_width+2*wall,wall]);
      translate([wall+.35,wall+.35,wall]) cube([inside_length-.7,inside_width-.7,2]);
    }
    translate([wall+2,wall+2,wall-.1]) cube([inside_length-4,inside_width-4,3]);
    for(x=[12:8:48]) translate([x,12,-1]) cube([3,12,wall+2]);
  }
}
if(part=="base" || part=="both") base();
if(part=="lid") lid();
if(part=="both") translate([0,inside_width+25,0]) lid();
