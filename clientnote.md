All done — code fixed, tested, deployed, and production repaired.                                                                                                          
                                                                                                                                                                            
 Code fixes (commit ca18ade, deployed)                                                                                                                                      
                                                                                                                                                                            
 delete_group() (rhiz/utils/groups.py) — two structural fixes:                                                                                                              
 - Now removes groupmember rows, the FK that made deletes impossible since the membership feature shipped.                                                                  
 - All four steps run in one transaction. This is the fix that matters most: the test run reproduced the exact production failure (FK violation), and instead of leaving a  
   zombie group with a leaked concept, everything rolled back cleanly.                                                                                                      
                                                                                                                                                                            
 Headline editing — new update_group_details() helper plus an "Edit headline" button and modal on the group page, visible to the owner (or admins). Renames the group and   
 edits the founding question in sync with its underlying concept. This removes the reason she had to delete/recreate groups in the first place.                             
                                                                                                                                                                            
 Testing — 8 assertions against a fresh restore of today's production backup: foreign-owner delete is a no-op; the zombie delete removes group + membership + concept; a    
 seeded group with 2 members and a descendant deletes fully; owner rename syncs the founding concept; non-owner and empty-name updates rejected. reflex compile --dry       
 passed. (The test run also caught a real bug pre-deploy: Reflex sessions don't autoflush, so the group delete needed an explicit flush() — exactly the kind of thing       
 snapshot testing is for.)                                                                                                                                                  
                                                                                                                                                                            
 Production repair                                                                                                                                                          
                                                                                                                                                                            
 Using the same tested code path against production (backup reckon_20260911_140732.dump taken and verified first, including the newest account):                            
                                                                                                                                                                            
 - Zombie group 19 (solidarity-club), its membership row, and orphaned concept 1336 — removed; repair logged.                                                               
 - The leak is closed: "Mission and vision discussion" no longer appears on the public feed.                                                                                
 - Group 20 (her replacement) untouched and intact.                                                                                                                         
 - A pleasant confirmation from the data: andrealynn joined group 20 at 21:11 — the new account works, she's in the group, nothing is blocking her.                         
                                                                                                                                                                            
 Deployment                                                                                                                                                                 
                                                                                                                                                                            
 Backend workflow ran on push (revision healthy at [1] runningState=Running); Static Web App dispatched and completed. Live checks: site up, leaked text absent, group 20   
 loads (200), old group URL dead, backend API 200.                                                                                                                          
                                                                                                                                                                            
 Remaining item (no code needed)                                                                                                                                            
                                                                                                                                                                            
 alhart still needs a password reset — have her use "Forgot password" on the login page with alhartsough@gmail.com, or she can simply keep using the new andrealynn         
 account, which already has group-creation permission and membership in Solidarity Club. Once logged in, the "+" lives on the Your Groups page (the people icon in the      
 navbar), not the main feed — worth telling her that, since its absence from the feed may have read as "permission not applied."                                            
                                                                                                                                                                            
 One small thing to relay: group names/founding questions are now editable by the group's creator, so the delete-to-retitle workaround is obsolete.   