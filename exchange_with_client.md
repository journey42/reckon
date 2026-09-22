I hope you’re well, and I hope you’re willing to do another round on this. I have bought a ticket to IIW #43, Nov 3. I have figured out a way to demo live, I think it will be really powerful and want to start testing with local groups as soon as I can. How difficult would it be to let people answer questions without signing up for accounts? I want to hide the legend icon in the Info dropdown menu and replace it with a tab to allow facilitators the ability to ask a question in a live room, throw the QR code and have people answer in the room. I would want to give the person who posed the question the ability to then close the question and have an artifact that is static get “published”. That would be part of its own universe, and not interact with the rest of the site.

That said, it would be great to be able to let any user who likes an answer publish it directly to the site, but depending on time, that’s a much lower priority. Is this something you’d be willing to spin up in the next couple weeks? How are assertions handled now, does the process without sign ups change the input and will that be a long job? Or is this something pretty simple given everything you’ve already built?


-------------


We have some of this. The data model already allows answers without accounts, the QR machinery is built, and the answer-processing pipeline is identical whether or not someone is signed in — so anonymous answers go through the same checks with no extra job to run. 

Can you answer the following:
                                                                                   When you say "its own universe" — should live-room answers be invisible everywhere on the site until published, even to you as admin? Or invisible to the public but visible to you for moderation? 
                                                             
 Should the artifact page be reachable by anyone with the link, forever? Or expire?                                                                                                                                                            
 When you say, " identity without accounts" do you mean fully anonymous, or name-optional pseudonyms typed at answer time? This changes the feel of the artifact a lot ("anonymous" vs "—  Maya, table 3") and changes moderation.                                                                                              
 Should one device be limited to one answer per question? (QR rooms get drive-by duplicates otherwise.)                            

 As regards facilitation, who can create a live question — anyone with an account, or only people who can create groups today?                               
 Can a facilitator delete individual answers while the room is live? (I'd assume yes, but it's your call whether it's visible that something was removed.)                                                                                                              
 One live question at a time per room, or several open in parallel?                                                                                               
 What should the artifact look like — question plus list of answers in order? Ranked by any likes received in the room? Your name/facilitator credit on it?                                                                                                                        
 Is the artifact a standalone page on rhiz.ai (e.g. /artifact/xxxx) or something exportable/printable?                              

 When a logged-in user publishes an anonymous answer to the site: into which group? Under whose name — theirs, with credit to the room? And does the original author get any say?                                          

 Will the room have reliable WIFI, or should the flow tolerate flaky connections? (It does degrade gracefully, but I'd test it.)


-------------


For Q&A live, invisible to the public and they don’t touch the rest of the site.

I would like to have access to them.

Reachable to anyone with the link, but frozen after the asker closes it out.

I want people who have not signed up for Rhiz to be able to answer the question without signing up. Fully anonymous, although I wonder if facilitators would want the option of requiring names and we could let them choose, but that’s maybe down the road.



One answer per device per question, editable until the facilitator closes the question.If someone submits an answer, closes out the window and clicks the QR again, can you send the device back to their answer to edit? They’ll be able to edit even if it already has upvotes. I’d like something added to the edited comment to show that it’s been edited.



I want people to be able to upvote other peoples answers, that would be unlimited, and no downvote for these smaller rooms. Also no comment sections.

I would like anyone with an account to be able to ask a question



Yes to deletion and to it being visible something was deleted, maybe a “Removed by facilitator” note.

Right now the room boundary is whatever person is facilitating, I think they can run more than one in parallel if they want.



Yes to format of: question with ranked responses. I’d like the responses ranked by support, I think with a note from the question asker at publishing time in case they want to tag it with anything.

Stand alone permanent page with a "print" stylesheet.

If someone pushes it to the site it shows up on the main Rhiz site as a new anonymous concept, but that’s not a priority presently.

Probably flaky connections as there will be 300 people there.



So, completely new user clicks QR code to answer, gets the asked question with an answer box under it, they answer and it submits directly to the page. I want them to answer before they see a list of answers. If they submit something very close to something someone’s already submitted answer I want their answer live in the room before they have to make a decision about supporting their own or someone else’s language. So once they submit that concept initially it should go right to the room, and they are then faced with a page of any similar results just like the main page, only in this context they may be more interested in the live convo, so they can ignore it. So if they withdraw it in favor of someone else’s it should go away (unless someone else has upvoted it) and they should add that upvote to the competing concept. So, 1 upvote from anyone will keep that answer in place.



After that workflow it should go to the live updating Q&A page. Can we have that page constantly updating showing answers and consolidation as it happens? So live answer with upvotes as they arrive or get deleted. Same screen for the facilitator and the participants. I’d like the facilitator to have the ability to click a concept if they feel the need to remove it, that way there’s no ugly delete button on everyone's screen.





I would like to change the wording of the warning to “Someone in the room said something similar. Would you like to support that instead?”



Can I have a similarity threshold dial so I can fine tune it at live events?