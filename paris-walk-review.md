# Paris walking-transfer review

This is a decision draft only; it does not alter the network. It covers all 152 unique cross-station walk pairs currently present in `network.json`. Directional duplicates are combined, while same-station transfer records are excluded.

## Proposed allow (24)

| From | To | Straight-line distance | Feed time (forward/reverse) | Rationale |
|---|---|---:|---:|---|
| Aéroport d’Orly (Terminaux 1-2-3) | Aéroport d’Orly (Terminal 4) | 521 m | 780s | Orly airport terminal connection |
| Auber | Opéra | 292 m | 251s | Auber–Opéra station complex |
| Bibliothèque François Mitterrand | Avenue de France | 543 m | 180s | Bibliothèque François Mitterrand–Avenue de France interchange |
| Boulainvilliers | La Muette | 180 m | 180s | Boulainvilliers–La Muette out-of-station interchange |
| Champ de Mars Tour Eiffel | Bir-Hakeim | 264 m | 300s | Champ de Mars–Bir-Hakeim interchange |
| Châtelet - Les Halles | Châtelet | 347 m | 346s | Châtelet station complex |
| Châtelet - Les Halles | Les Halles | 151 m | 180s | Châtelet–Les Halles station complex |
| Gare du Nord | Gare de l'Est | 471 m | 315s | Gare du Nord–Gare de l’Est pedestrian interchange |
| Gare du Nord | La Chapelle | 549 m | 444/400s | Gare du Nord–La Chapelle out-of-station interchange |
| Gare du Nord | Magenta | 150 m | 206s | Gare du Nord–Magenta station complex |
| Gare Montparnasse | Montparnasse Bienvenue | 395 m | 337/332s | Montparnasse station complex |
| Gare Montparnasse | Montparnasse Bienvenue | 403 m | 330/314s | Montparnasse station complex |
| Gare Saint-Lazare | Saint-Augustin | 385 m | 392s | Saint-Lazare–Saint-Augustin station complex |
| Haussmann Saint-Lazare | Auber | 251 m | 300s | Haussmann Saint-Lazare–Auber station complex |
| Haussmann Saint-Lazare | Gare Saint-Lazare | 231 m | 304s | Haussmann Saint-Lazare–Gare Saint-Lazare complex |
| Haussmann Saint-Lazare | Havre - Caumartin | 193 m | 328s | Haussmann Saint-Lazare–Havre-Caumartin complex |
| Havre - Caumartin | Auber | 160 m | 263s | Havre-Caumartin–Auber station complex |
| Havre - Caumartin | Gare Saint-Lazare | 287 m | 338s | Havre-Caumartin–Gare Saint-Lazare complex |
| Jules Joffrin | Jules Joffrin | 12 m | 60s | Duplicate Jules Joffrin records |
| Montparnasse Bienvenue | Montparnasse Bienvenue | 8 m | 10s | Duplicate Montparnasse Bienvenue records |
| Musée d'Orsay | Solférino | 299 m | 420s | Musée d’Orsay–Solférino interchange |
| Porte Dauphine | Avenue Foch | 169 m | 150s | Porte Dauphine–Avenue Foch interchange |
| Porte de Clichy - Tribunal de Paris | Porte de Clichy | 26 m | 216s | Duplicate Porte de Clichy records |
| Saint-Michel Notre-Dame | Cluny - La Sorbonne | 258 m | 336s | Saint-Michel Notre-Dame–Cluny station complex |

## Proposed reject (128)

| From | To | Straight-line distance | Feed time (forward/reverse) | Rationale |
|---|---|---:|---:|---|
| Alcide d'Orbigny | Mairie de Pierrefitte | 367 m | 358s | Ordinary nearby stations; no recognized interchange identified |
| Anny Flore | Neuilly - Porte Maillot | 363 m | 314s | Ordinary nearby stations; no recognized interchange identified |
| Arts et Métiers | Réaumur - Sébastopol | 345 m | 377s | Ordinary nearby stations; no recognized interchange identified |
| Avenue Émile Zola | Commerce | 279 m | 358s | Ordinary nearby stations; no recognized interchange identified |
| Avenue Émile Zola | La Motte-Picquet - Grenelle | 371 m | 380s | Ordinary nearby stations; no recognized interchange identified |
| Avron | Buzenval | 223 m | 284s | Ordinary nearby stations; no recognized interchange identified |
| Bercy | Dugommier | 591 m | 322s | Ordinary nearby stations; no recognized interchange identified |
| Bir-Hakeim | Dupleix | 434 m | 369s | Ordinary nearby stations; no recognized interchange identified |
| Bolivar | Jaurès | 301 m | 378s | Ordinary nearby stations; no recognized interchange identified |
| Brancion | Porte de Vanves | 357 m | 365s | Ordinary nearby stations; no recognized interchange identified |
| Butte Pinson (Parc Régional) | Jacques Prévert | 296 m | 338s | Ordinary nearby stations; no recognized interchange identified |
| Camille Groult | Constant Coquelin | 304 m | 361s | Ordinary nearby stations; no recognized interchange identified |
| Cardinal Lemoine | Jussieu | 248 m | 341s | Ordinary nearby stations; no recognized interchange identified |
| César | Blumenthal | 285 m | 358s | Ordinary nearby stations; no recognized interchange identified |
| Chardon Lagache | Église d'Auteuil | 316 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Charles de Gaulle - Étoile | Argentine | 443 m | 336s | Ordinary nearby stations; no recognized interchange identified |
| Charles de Gaulle - Étoile | George V | 443 m | 376s | Ordinary nearby stations; no recognized interchange identified |
| Charles de Gaulle - Étoile | Kléber | 335 m | 286s | Ordinary nearby stations; no recognized interchange identified |
| Châteaudun - Barbès | Cimetière Parisien d'Ivry | 385 m | 349s | Ordinary nearby stations; no recognized interchange identified |
| Châteaudun - Barbès | Porte de Choisy | 510 m | 374s | Ordinary nearby stations; no recognized interchange identified |
| Châtelet | Hôtel de Ville | 367 m | 307s | Ordinary nearby stations; no recognized interchange identified |
| Châtelet - Les Halles | Etienne Marcel | 303 m | 341s | Ordinary nearby stations; no recognized interchange identified |
| Chaussée d'Antin - La Fayette | Opéra | 279 m | 348s | Ordinary nearby stations; no recognized interchange identified |
| Chemin Vert | Bréguet-Sabin | 198 m | 231s | Ordinary nearby stations; no recognized interchange identified |
| Chemin Vert | Richard-Lenoir | 350 m | 310s | Ordinary nearby stations; no recognized interchange identified |
| Chevilly-Larue (Marché International) | La Belle Épine | 391 m | 540s | Ordinary nearby stations; no recognized interchange identified |
| Choisy-le-Roi | Rouget de Lisle | 380 m | 368s | Ordinary nearby stations; no recognized interchange identified |
| Cimetière de Saint-Denis | Basilique de Saint-Denis | 316 m | 353s | Ordinary nearby stations; no recognized interchange identified |
| Cluny - La Sorbonne | Maubert - Mutualité | 322 m | 325s | Ordinary nearby stations; no recognized interchange identified |
| Colette Besson | Porte d'Aubervilliers | 429 m | 366s | Ordinary nearby stations; no recognized interchange identified |
| Commerce | Félix Faure | 246 m | 325s | Ordinary nearby stations; no recognized interchange identified |
| Corvisart | Glacière | 454 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Desnouettes | Porte de Versailles | 359 m | 374s | Ordinary nearby stations; no recognized interchange identified |
| Edgar Quinet | Vavin | 304 m | 365s | Ordinary nearby stations; no recognized interchange identified |
| Église d'Auteuil | Mirabeau | 271 m | 368s | Ordinary nearby stations; no recognized interchange identified |
| Ella Fitzgerald | Pantin | 425 m | 482/484s | Ordinary nearby stations; no recognized interchange identified |
| Escadrille Normandie - Niémen | Gaston Roulaud | 374 m | 322s | Ordinary nearby stations; no recognized interchange identified |
| Escadrille Normandie - Niémen | La Ferme | 364 m | 340s | Ordinary nearby stations; no recognized interchange identified |
| Etienne Marcel | Les Halles | 332 m | 312s | Ordinary nearby stations; no recognized interchange identified |
| Falguière | Duroc | 283 m | 351s | Ordinary nearby stations; no recognized interchange identified |
| Gare de l'Est | Château Landon | 352 m | 213s | Ordinary nearby stations; no recognized interchange identified |
| Gare de l'Est | Magenta | 440 m | 326s | Ordinary nearby stations; no recognized interchange identified |
| Gare de Lyon | Quai de la Rapée | 500 m | 302s | Ordinary nearby stations; no recognized interchange identified |
| Gare Saint-Lazare | Europe | 408 m | 274s | Ordinary nearby stations; no recognized interchange identified |
| Gare Saint-Lazare | Liège | 444 m | 342s | Ordinary nearby stations; no recognized interchange identified |
| Hôpital Robert Debré | Pré-Saint-Gervais | 187 m | 303s | Ordinary nearby stations; no recognized interchange identified |
| Hôtel de Ville de Bobigny | Libération | 344 m | 373s | Ordinary nearby stations; no recognized interchange identified |
| Jacques Bonsergent | Château d'Eau | 383 m | 343s | Ordinary nearby stations; no recognized interchange identified |
| Jacques Bonsergent | République | 412 m | 272s | Ordinary nearby stations; no recognized interchange identified |
| Jardin Parisien | Hôpital Béclère | 344 m | 326s | Ordinary nearby stations; no recognized interchange identified |
| Joncherolles | Suzanne Valadon | 386 m | 307s | Ordinary nearby stations; no recognized interchange identified |
| La Courneuve - 8 Mai 1945 | Maurice Lachâtre | 293 m | 358s | Ordinary nearby stations; no recognized interchange identified |
| La Croix de Berny | Antony | 835 m | 900s | Ordinary nearby stations; no recognized interchange identified |
| La Motte-Picquet - Grenelle | Cambronne | 279 m | 271s | Ordinary nearby stations; no recognized interchange identified |
| Lacépède | Gilbert Bonnemaison | 287 m | 342s | Ordinary nearby stations; no recognized interchange identified |
| Les Béatus | Rose Bertin | 355 m | 341s | Ordinary nearby stations; no recognized interchange identified |
| Les Flanades | Les Cholettes | 459 m | 375s | Ordinary nearby stations; no recognized interchange identified |
| Les Peintres | Cité-Jardin | 413 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Mabillon | Saint-Germain-des-Prés | 148 m | –/137s | Ordinary nearby stations; no recognized interchange identified |
| Mairie de Vélizy | Louvois | 338 m | 343s | Ordinary nearby stations; no recognized interchange identified |
| Mairie de Vitry-sur-Seine | Musée MAC VAL | 393 m | 346s | Ordinary nearby stations; no recognized interchange identified |
| Marché de Saint-Denis | Basilique de Saint-Denis | 322 m | 377s | Ordinary nearby stations; no recognized interchange identified |
| Maryse Bastié | Avenue de France | 357 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Michel-Ange - Molitor | Exelmans | 300 m | 366s | Ordinary nearby stations; no recognized interchange identified |
| Monceau | Malesherbes | 273 m | 316s | Ordinary nearby stations; no recognized interchange identified |
| Montsouris | Cité Universitaire | 396 m | 378s | Ordinary nearby stations; no recognized interchange identified |
| Musée de Sèvres | Pont de Sèvres | 485 m | 459s | Ordinary nearby stations; no recognized interchange identified |
| Nanterre-La-Folie | Nanterre Préfecture | 383 m | 322s | Ordinary nearby stations; no recognized interchange identified |
| Notre-Dame-de-Lorette | Saint-Georges | 264 m | 334s | Ordinary nearby stations; no recognized interchange identified |
| Notre-Dame-des-Champs | Saint-Placide | 261 m | 318s | Ordinary nearby stations; no recognized interchange identified |
| Notre-Dame-des-Champs | Vavin | 314 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Noveos | Parc des Sports | 327 m | 287s | Ordinary nearby stations; no recognized interchange identified |
| Oberkampf | Filles du Calvaire | 234 m | 282s | Ordinary nearby stations; no recognized interchange identified |
| Odéon | Saint-Michel Notre-Dame | 360 m | 378s | Ordinary nearby stations; no recognized interchange identified |
| Opéra | Quatre Septembre | 364 m | 366s | Ordinary nearby stations; no recognized interchange identified |
| Palais Royal - Musée du Louvre | Louvre - Rivoli | 360 m | 341s | Ordinary nearby stations; no recognized interchange identified |
| Parc de Saint-Cloud | Boulogne Pont de Saint-Cloud | 510 m | 660s | Ordinary nearby stations; no recognized interchange identified |
| Pasteur | Sèvres-Lecourbe | 336 m | 336s | Ordinary nearby stations; no recognized interchange identified |
| Paul Valéry | Les Flanades | 285 m | 265s | Ordinary nearby stations; no recognized interchange identified |
| Pigalle | Abbesses | 253 m | 328s | Ordinary nearby stations; no recognized interchange identified |
| Place Monge | Censier - Daubenton | 332 m | 347s | Ordinary nearby stations; no recognized interchange identified |
| Porte d'Italie | Maison Blanche | 368 m | 327s | Ordinary nearby stations; no recognized interchange identified |
| Porte d'Italie | Porte de Choisy | 356 m | 374s | Ordinary nearby stations; no recognized interchange identified |
| Porte d'Ivry | Porte de Choisy | 406 m | 358s | Ordinary nearby stations; no recognized interchange identified |
| Porte de Charenton | Porte Dorée | 483 m | 377s | Ordinary nearby stations; no recognized interchange identified |
| Porte de Saint-Ouen | Epinettes - Pouchet | 358 m | 367s | Ordinary nearby stations; no recognized interchange identified |
| Pyrénées | Jourdain | 324 m | 340s | Ordinary nearby stations; no recognized interchange identified |
| Rambuteau | Etienne Marcel | 397 m | 333s | Ordinary nearby stations; no recognized interchange identified |
| Rambuteau | Hôtel de Ville | 431 m | 349s | Ordinary nearby stations; no recognized interchange identified |
| Raspail | Vavin | 363 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Réaumur - Sébastopol | Etienne Marcel | 343 m | 328s | Ordinary nearby stations; no recognized interchange identified |
| République | Temple | 204 m | 334s | Ordinary nearby stations; no recognized interchange identified |
| Richard-Lenoir | Bréguet-Sabin | 369 m | 258s | Ordinary nearby stations; no recognized interchange identified |
| Richard-Lenoir | Saint-Ambroise | 320 m | 294s | Ordinary nearby stations; no recognized interchange identified |
| Richelieu - Drouot | Quatre Septembre | 300 m | 353s | Ordinary nearby stations; no recognized interchange identified |
| Roger Semât | Baudelaire | 277 m | 335s | Ordinary nearby stations; no recognized interchange identified |
| Rosa Parks | Porte d'Aubervilliers | 358 m | 315s | Ordinary nearby stations; no recognized interchange identified |
| Rue du Bac | Solférino | 346 m | 352s | Ordinary nearby stations; no recognized interchange identified |
| Saarinen | Porte de Rungis | 286 m | 346s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Denis - Pleyel | Carrefour Pleyel | 290 m | 446s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Denis - Pleyel | Stade de France Saint-Denis | 348 m | 840s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Denis - Porte de Paris | Pierre de Geyter | 357 m | 342s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Fargeau | Adrienne Bolland | 342 m | 339s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Jacques | Denfert-Rochereau | 352 m | 366s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Marcel | Campo-Formio | 385 m | 371s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Michel Notre-Dame | Châtelet | 607 m | 780s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Michel Notre-Dame | Cité | 278 m | 403s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Placide | Rennes | 194 m | 240s | Ordinary nearby stations; no recognized interchange identified |
| Saint-Sébastien - Froissart | Filles du Calvaire | 227 m | 301s | Ordinary nearby stations; no recognized interchange identified |
| Ségur | Sèvres-Lecourbe | 286 m | 310s | Ordinary nearby stations; no recognized interchange identified |
| Sèvres - Babylone | Saint-Sulpice | 330 m | 352s | Ordinary nearby stations; no recognized interchange identified |
| Simplon | Jules Joffrin | 285 m | 373s | Ordinary nearby stations; no recognized interchange identified |
| Simplon | Jules Joffrin | 297 m | 373s | Ordinary nearby stations; no recognized interchange identified |
| Simplon | Marcadet - Poissonniers | 373 m | 320s | Ordinary nearby stations; no recognized interchange identified |
| Solférino | Assemblée Nationale | 338 m | 381s | Ordinary nearby stations; no recognized interchange identified |
| Square Sainte-Odile | Péreire Levallois | 262 m | 282s | Ordinary nearby stations; no recognized interchange identified |
| Square Sainte-Odile | Porte de Champerret | 311 m | 338s | Ordinary nearby stations; no recognized interchange identified |
| Stade Charléty - Porte de Gentilly | Cité Universitaire | 418 m | 371s | Ordinary nearby stations; no recognized interchange identified |
| Stalingrad | Jaurès | 314 m | 304s | Ordinary nearby stations; no recognized interchange identified |
| Strasbourg - Saint-Denis | Château d'Eau | 367 m | 356s | Ordinary nearby stations; no recognized interchange identified |
| Suzanne Lenglen | Balard | 297 m | 372s | Ordinary nearby stations; no recognized interchange identified |
| Suzanne Lenglen | Porte d'Issy | 345 m | 377s | Ordinary nearby stations; no recognized interchange identified |
| Théâtre Gérard Philipe | Paul Éluard | 383 m | 338s | Ordinary nearby stations; no recognized interchange identified |
| Théâtre Gérard Philipe | Saint-Denis | 430 m | 329s | Ordinary nearby stations; no recognized interchange identified |
| Vallée aux Loups | Cité-Jardin | 379 m | 364s | Ordinary nearby stations; no recognized interchange identified |
| Vélizy 2 | Dewoitine | 372 m | 300s | Ordinary nearby stations; no recognized interchange identified |
| Villetaneuse - Université | Pablo Neruda | 381 m | 377s | Ordinary nearby stations; no recognized interchange identified |
| Vincennes | Bérault | 331 m | 600s | Ordinary nearby stations; no recognized interchange identified |
