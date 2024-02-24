"""help page."""
import reflex as rx
from reckon.layouts import info_layout
from reckon.state.base import AppState
from reckon.styles import page_params

def info_page(*args, **kwargs):
    return info_layout(
            rx.markdown(
                *args,
                font_size="1xl",
                font_weight="normal",
                mb=4,
                border_x="1px solid #ededed",
                h="100%",
            )
    )

about_text = """
**About**

Reckon was founded with the goal of encouraging both independent thought and broad consensus. The aim is to reduce political polarity and allow people to find common ground wherever possible. The hope is that destructive and harmful ideology aimed at groups or individuals will naturally be ratioed by our users, in the event this is not how the site functions automatically, we encourage you to make us of our red flag system. This is the first attempt at testing this system of discourse, the final product will have more and different features when deployed at scale. This system is entirely anonymous between users. It was designed this way to way to afford people the opportunity to express themselves without risk of being singled out. Your concepts will only be uncovered if people have ideas along the same lines. We encourage you to submit any thoughts you feel strongly about, even if they don’t presently have traction.  While the obvious application of this system is politics, if you choose to fight over the blue or gold dress or the particular merits of food groups or music genres the site will raise no objection.

Instructions:

Step one 1) Enter a proposal or statement of principle

Step 2) Your submission will be ranked by cosine similarity with any similar submissions. It is possible with such a small user base that proposals in opposition to each other will rank in the same search. Feel free to downvote accordingly. The first concept on the results page will always be your submission in your exact words. If you spot a concept that you prefer the phrasing of, or one that has already picked up traction and is something you can agree with you can choose to upvote that concept or stick with your original wording. If you downvote a concept you will remain on the results page unless you also click onto that concept page. If you upvote a concept it will take you to that concept page with its comments section. This is to encourage winnowing of concepts and active discussion.

Step 3) The comments section is intended to collect arguments regarding a particular concept. To submit a comment you will select between 3 buttons that indicate support, opposition or a neutral “point of order”. If you start a new thread the first comment indicates your attitude towards the concept. A reply to a comment will automatically upvote or downvote that comment. It’s possible to be in support of a concept, but opposed to a particular argument regarding that concept. The comments section is designed to reflect that.

Concepts will also have a refresh button which allows you to run that concept back through the semantic similarity search. If you run a search on a concept different from what you originally searched you will not necessarily receive the same results. The concept you have refreshed will now be the first result, with subsequent results ranked in orientation to the refreshed concept.
You are free to edit or delete your concepts and comments up until they have been voted on by others. At that point you can withdraw your support or opposition, but as they already have traction with others they will remain on the site.

The trending icon at the top of the page will take you to the most popular concepts. The floppy disk will take you to your own vote and comment history.
Under the navigation menu there is an option to submit any concerns or suggestions regarding the rhetorical process of the site, or to report a technical problem. If you have concerns about the content of a particular concept or comment please use the red flag feature.
"""

@rx.page(on_load=AppState.check_login(), **page_params)
def about():
    """The about page."""
    return info_page(about_text)

guidelines_text = """
**Guidelines**

A note on brigading courtesy of dictionary.com:

*Brigading* is a slang term for an online practice in which people band together to perform a coordinated action, especially a negative one, such as manipulating a vote or poll or harassing a specific person or members of an online community.

The trouble with brigading is not that it’s mean, or that it targets individuals. The real trouble is that it clogs up forums choking out genuine discourse, dissuading the well intentioned from engaging. Reckon is refined brigading. This site will allow peoples better impulses to display themselves without risk of being viewed as cringe or corny. Reckon is safety in numbers. My hope is that those with malice will simply be ratioed into oblivion. The flip side of this is that if no one agrees with your position it will also vanish into oblivion. This frees everyone up to express their true beliefs. The bet I’m making is that a solid majority of humans have good intentions, and that this process will allow those intentions to shine through without any individual having to risk the judgement of the almighty internet.
"""

@rx.page(on_load=AppState.check_login(), **page_params)
def guidelines():
    """The guidlines page."""
    return info_page(guidelines_text)

terms_text = """
**Terms and Conditions**

Last updated: 2024-01-24

1. **Introduction**

Welcome to **Reckon Forum** (“Company”, “we”, “our”, “us”)!

These Terms of Service (“Terms”, “Terms of Service”) govern your use of our website located at **reckonsoc.com** (together or individually “Service”) operated by **Reckon Forum**.

Our Privacy Policy also governs your use of our Service and explains how we collect, safeguard and disclose information that results from your use of our web pages.

Your agreement with us includes these Terms and our Privacy Policy (“Agreements”). You acknowledge that you have read and understood Agreements, and agree to be bound of them.

If you do not agree with (or cannot comply with) Agreements, then you may not use the Service, but please let us know by emailing at **support@reckon.cc** so we can try to find a solution. These Terms apply to all visitors, users and others who wish to access or use Service.

1. **Communications**

By using our Service, you agree to subscribe to newsletters, marketing or promotional materials and other information we may send. However, you may opt out of receiving any, or all, of these communications from us by following the unsubscribe link or by emailing at support@reckon.cc.

1. **Contests, Sweepstakes and Promotions**

Any contests, sweepstakes or other promotions (collectively, “Promotions”) made available through Service may be governed by rules that are separate from these Terms of Service. If you participate in any Promotions, please review the applicable rules as well as our Privacy Policy. If the rules for a Promotion conflict with these Terms of Service, Promotion rules will apply.

1. **Content**

Our Service allows you to post, link, store, share and otherwise make available certain information, text, graphics, videos, or other material (“Content”). You are responsible for Content that you post on or through Service, including its legality, reliability, and appropriateness.

By posting Content on or through Service, You represent and warrant that: (i) Content is yours (you own it) and/or you have the right to use it and the right to grant us the rights and license as provided in these Terms, and (ii) that the posting of your Content on or through Service does not violate the privacy rights, publicity rights, copyrights, contract rights or any other rights of any person or entity. We reserve the right to terminate the account of anyone found to be infringing on a copyright.

You retain any and all of your rights to any Content you submit, post or display on or through Service and you are responsible for protecting those rights. We take no responsibility and assume no liability for Content you or any third party posts on or through Service. However, by posting Content using Service you grant us the right and license to use, modify, publicly perform, publicly display, reproduce, and distribute such Content on and through Service. You agree that this license includes the right for us to make your Content available to other users of Service, who may also use your Content subject to these Terms.

Reckon Forum has the right but not the obligation to monitor and edit all Content provided by users.

In addition, Content found on or through this Service are the property of Reckon Forum or used with permission. You may not distribute, modify, transmit, reuse, download, repost, copy, or use said Content, whether in whole or in part, for commercial purposes or for personal gain, without express advance written permission from us.

1. **Prohibited Uses**

You may use Service only for lawful purposes and in accordance with Terms. You agree not to use Service:

0.1. In any way that violates any applicable national or international law or regulation.

0.2. For the purpose of exploiting, harming, or attempting to exploit or harm minors in any way by exposing them to inappropriate content or otherwise.

0.3. To transmit, or procure the sending of, any advertising or promotional material, including any “junk mail”, “chain letter,” “spam,” or any other similar solicitation.

0.4. To impersonate or attempt to impersonate Company, a Company employee, another user, or any other person or entity.

0.5. In any way that infringes upon the rights of others, or in any way is illegal, threatening, fraudulent, or harmful, or in connection with any unlawful, illegal, fraudulent, or harmful purpose or activity.

0.6. To engage in any other conduct that restricts or inhibits anyone’s use or enjoyment of Service, or which, as determined by us, may harm or offend Company or users of Service or expose them to liability.

Additionally, you agree not to:

0.1. Use Service in any manner that could disable, overburden, damage, or impair Service or interfere with any other party’s use of Service, including their ability to engage in real time activities through Service.

0.2. Use any robot, spider, or other automatic device, process, or means to access Service for any purpose, including monitoring or copying any of the material on Service.

0.3. Use any manual process to monitor or copy any of the material on Service or for any other unauthorized purpose without our prior written consent.

0.4. Use any device, software, or routine that interferes with the proper working of Service.

0.5. Introduce any viruses, trojan horses, worms, logic bombs, or other material which is malicious or technologically harmful.

0.6. Attempt to gain unauthorized access to, interfere with, damage, or disrupt any parts of Service, the server on which Service is stored, or any server, computer, or database connected to Service.

0.7. Attack Service via a denial-of-service attack or a distributed denial-of-service attack.

0.8. Take any action that may damage or falsify Company rating.

0.9. Otherwise attempt to interfere with the proper working of Service.

1. **Analytics**

We may use third-party Service Providers to monitor and analyze the use of our Service.

1. **No Use By Minors**

Service is intended only for access and use by individuals at least eighteen (18) years old. By accessing or using Service, you warrant and represent that you are at least eighteen (18) years of age and with the full authority, right, and capacity to enter into this agreement and abide by all of the terms and conditions of Terms. If you are not at least eighteen (18) years old, you are prohibited from both the access and usage of Service.

1. **Accounts**

When you create an account with us, you guarantee that you are above the age of 18, and that the information you provide us is accurate, complete, and current at all times. Inaccurate, incomplete, or obsolete information may result in the immediate termination of your account on Service.

You are responsible for maintaining the confidentiality of your account and password, including but not limited to the restriction of access to your computer and/or account. You agree to accept responsibility for any and all activities or actions that occur under your account and/or password, whether your password is with our Service or a third-party service. You must notify us immediately upon becoming aware of any breach of security or unauthorized use of your account.

You may not use as a username the name of another person or entity or that is not lawfully available for use, a name or trademark that is subject to any rights of another person or entity other than you, without appropriate authorization. You may not use as a username any name that is offensive, vulgar or obscene.

We reserve the right to refuse service, terminate accounts, remove or edit content, or cancel orders in our sole discretion.

1. **Intellectual Property**

Service and its original content (excluding Content provided by users), features and functionality are and will remain the exclusive property of Reckon Forum and its licensors. Service is protected by copyright, trademark, and other laws of and foreign countries. Our trademarks may not be used in connection with any product or service without the prior written consent of Reckon Forum.

1. **Copyright Policy**

We respect the intellectual property rights of others. It is our policy to respond to any claim that Content posted on Service infringes on the copyright or other intellectual property rights (“Infringement”) of any person or entity.

If you are a copyright owner, or authorized on behalf of one, and you believe that the copyrighted work has been copied in a way that constitutes copyright infringement, please submit your claim via email to support@reckon.cc, with the subject line: “Copyright Infringement” and include in your claim a detailed description of the alleged Infringement as detailed below, under “DMCA Notice and Procedure for Copyright Infringement Claims”

You may be held accountable for damages (including costs and attorneys’ fees) for misrepresentation or bad-faith claims on the infringement of any Content found on and/or through Service on your copyright.

1. **DMCA Notice and Procedure for Copyright Infringement Claims**

You may submit a notification pursuant to the Digital Millennium Copyright Act (DMCA) by providing our Copyright Agent with the following information in writing (see 17 U.S.C 512(c)(3) for further detail):

0.1. an electronic or physical signature of the person authorized to act on behalf of the owner of the copyright’s interest;

0.2. a description of the copyrighted work that you claim has been infringed, including the URL (i.e., web page address) of the location where the copyrighted work exists or a copy of the copyrighted work;

0.3. identification of the URL or other specific location on Service where the material that you claim is infringing is located;

0.4. your address, telephone number, and email address;

0.5. a statement by you that you have a good faith belief that the disputed use is not authorized by the copyright owner, its agent, or the law;

0.6. a statement by you, made under penalty of perjury, that the above information in your notice is accurate and that you are the copyright owner or authorized to act on the copyright owner’s behalf.

You can contact our Copyright Agent via email at support@reckon.cc.

1. **Error Reporting and Feedback**

You may provide us either directly at support@reckon.cc or via third party sites and tools with information and feedback concerning errors, suggestions for improvements, ideas, problems, complaints, and other matters related to our Service (“Feedback”). You acknowledge and agree that: (i) you shall not retain, acquire or assert any intellectual property right or other right, title or interest in or to the Feedback; (ii) Company may have development ideas similar to the Feedback; (iii) Feedback does not contain confidential information or proprietary information from you or any third party; and (iv) Company is not under any obligation of confidentiality with respect to the Feedback. In the event the transfer of the ownership to the Feedback is not possible due to applicable mandatory laws, you grant Company and its affiliates an exclusive, transferable, irrevocable, free-of-charge, sub-licensable, unlimited and perpetual right to use (including copy, modify, create derivative works, publish, distribute and commercialize) Feedback in any manner and for any purpose.

1. **Links To Other Web Sites**

Our Service may contain links to third party web sites or services that are not owned or controlled by Reckon Forum.

Reckon Forum has no control over, and assumes no responsibility for the content, privacy policies, or practices of any third party web sites or services. We do not warrant the offerings of any of these entities/individuals or their websites.


YOU ACKNOWLEDGE AND AGREE THAT COMPANY SHALL NOT BE RESPONSIBLE OR LIABLE, DIRECTLY OR INDIRECTLY, FOR ANY DAMAGE OR LOSS CAUSED OR ALLEGED TO BE CAUSED BY OR IN CONNECTION WITH USE OF OR RELIANCE ON ANY SUCH CONTENT, GOODS OR SERVICES AVAILABLE ON OR THROUGH ANY SUCH THIRD PARTY WEB SITES OR SERVICES.

WE STRONGLY ADVISE YOU TO READ THE TERMS OF SERVICE AND PRIVACY POLICIES OF ANY THIRD PARTY WEB SITES OR SERVICES THAT YOU VISIT.

1. **Disclaimer Of Warranty**

THESE SERVICES ARE PROVIDED BY COMPANY ON AN “AS IS” AND “AS AVAILABLE” BASIS. COMPANY MAKES NO REPRESENTATIONS OR WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, AS TO THE OPERATION OF THEIR SERVICES, OR THE INFORMATION, CONTENT OR MATERIALS INCLUDED THEREIN. YOU EXPRESSLY AGREE THAT YOUR USE OF THESE SERVICES, THEIR CONTENT, AND ANY SERVICES OR ITEMS OBTAINED FROM US IS AT YOUR SOLE RISK.

NEITHER COMPANY NOR ANY PERSON ASSOCIATED WITH COMPANY MAKES ANY WARRANTY OR REPRESENTATION WITH RESPECT TO THE COMPLETENESS, SECURITY, RELIABILITY, QUALITY, ACCURACY, OR AVAILABILITY OF THE SERVICES. WITHOUT LIMITING THE FOREGOING, NEITHER COMPANY NOR ANYONE ASSOCIATED WITH COMPANY REPRESENTS OR WARRANTS THAT THE SERVICES, THEIR CONTENT, OR ANY SERVICES OR ITEMS OBTAINED THROUGH THE SERVICES WILL BE ACCURATE, RELIABLE, ERROR-FREE, OR UNINTERRUPTED, THAT DEFECTS WILL BE CORRECTED, THAT THE SERVICES OR THE SERVER THAT MAKES IT AVAILABLE ARE FREE OF VIRUSES OR OTHER HARMFUL COMPONENTS OR THAT THE SERVICES OR ANY SERVICES OR ITEMS OBTAINED THROUGH THE SERVICES WILL OTHERWISE MEET YOUR NEEDS OR EXPECTATIONS.

COMPANY HEREBY DISCLAIMS ALL WARRANTIES OF ANY KIND, WHETHER EXPRESS OR IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF MERCHANTABILITY, NON-INFRINGEMENT, AND FITNESS FOR PARTICULAR PURPOSE.

THE FOREGOING DOES NOT AFFECT ANY WARRANTIES WHICH CANNOT BE EXCLUDED OR LIMITED UNDER APPLICABLE LAW.

1. **Limitation Of Liability**

EXCEPT AS PROHIBITED BY LAW, YOU WILL HOLD US AND OUR OFFICERS, DIRECTORS, EMPLOYEES, AND AGENTS HARMLESS FOR ANY INDIRECT, PUNITIVE, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGE, HOWEVER IT ARISES (INCLUDING ATTORNEYS’ FEES AND ALL RELATED COSTS AND EXPENSES OF LITIGATION AND ARBITRATION, OR AT TRIAL OR ON APPEAL, IF ANY, WHETHER OR NOT LITIGATION OR ARBITRATION IS INSTITUTED), WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE, OR OTHER TORTIOUS ACTION, OR ARISING OUT OF OR IN CONNECTION WITH THIS AGREEMENT, INCLUDING WITHOUT LIMITATION ANY CLAIM FOR PERSONAL INJURY OR PROPERTY DAMAGE, ARISING FROM THIS AGREEMENT AND ANY VIOLATION BY YOU OF ANY FEDERAL, STATE, OR LOCAL LAWS, STATUTES, RULES, OR REGULATIONS, EVEN IF COMPANY HAS BEEN PREVIOUSLY ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. EXCEPT AS PROHIBITED BY LAW, IF THERE IS LIABILITY FOUND ON THE PART OF COMPANY, IT WILL BE LIMITED TO THE AMOUNT PAID FOR THE PRODUCTS AND/OR SERVICES, AND UNDER NO CIRCUMSTANCES WILL THERE BE CONSEQUENTIAL OR PUNITIVE DAMAGES. SOME STATES DO NOT ALLOW THE EXCLUSION OR LIMITATION OF PUNITIVE, INCIDENTAL OR CONSEQUENTIAL DAMAGES, SO THE PRIOR LIMITATION OR EXCLUSION MAY NOT APPLY TO YOU.

1. **Termination**

We may terminate or suspend your account and bar access to Service immediately, without prior notice or liability, under our sole discretion, for any reason whatsoever and without limitation, including but not limited to a breach of Terms.

If you wish to terminate your account, you may simply discontinue using Service.

All provisions of Terms which by their nature should survive termination shall survive termination, including, without limitation, ownership provisions, warranty disclaimers, indemnity and limitations of liability.

1. **Governing Law**

These Terms shall be governed and construed in accordance with the laws of United States, which governing law applies to agreement without regard to its conflict of law provisions.

Our failure to enforce any right or provision of these Terms will not be considered a waiver of those rights. If any provision of these Terms is held to be invalid or unenforceable by a court, the remaining provisions of these Terms will remain in effect. These Terms constitute the entire agreement between us regarding our Service and supersede and replace any prior agreements we might have had between us regarding Service.

1. **Changes To Service**

We reserve the right to withdraw or amend our Service, and any service or material we provide via Service, in our sole discretion without notice. We will not be liable if for any reason all or any part of Service is unavailable at any time or for any period. From time to time, we may restrict access to some parts of Service, or the entire Service, to users, including registered users.

1. **Amendments To Terms**

We may amend Terms at any time by posting the amended terms on this site. It is your responsibility to review these Terms periodically.

Your continued use of the Platform following the posting of revised Terms means that you accept and agree to the changes. You are expected to check this page frequently so you are aware of any changes, as they are binding on you.

By continuing to access or use our Service after any revisions become effective, you agree to be bound by the revised terms. If you do not agree to the new terms, you are no longer authorized to use Service.

1. **Waiver And Severability**

No waiver by Company of any term or condition set forth in Terms shall be deemed a further or continuing waiver of such term or condition or a waiver of any other term or condition, and any failure of Company to assert a right or provision under Terms shall not constitute a waiver of such right or provision.

If any provision of Terms is held by a court or other tribunal of competent jurisdiction to be invalid, illegal or unenforceable for any reason, such provision shall be eliminated or limited to the minimum extent such that the remaining provisions of Terms will continue in full force and effect.

1. **Acknowledgement**

BY USING SERVICE OR OTHER SERVICES PROVIDED BY US, YOU ACKNOWLEDGE THAT YOU HAVE READ THESE TERMS OF SERVICE AND AGREE TO BE BOUND BY THEM.

1. **Contact Us**

Please send your feedback, comments, requests for technical support by email: **support@reckon.cc**.
"""

@rx.page(on_load=AppState.check_login(), **page_params)
def terms():
    """The terms page."""
    return info_page(terms_text)

privacy_text = """
**Privacy Policy**

Effective date: 2024-01-24

1. **Introduction**

Welcome to **Reckon**.

**Reckon** (“us”, “we”, or “our”) operates **reckonsoc.com** (hereinafter referred to as **“Service”**).

Our Privacy Policy governs your visit to **reckonsoc.com**, and explains how we collect, safeguard and disclose information that results from your use of our Service.

We use your data to provide and improve Service. By using Service, you agree to the collection and use of information in accordance with this policy. Unless otherwise defined in this Privacy Policy, the terms used in this Privacy Policy have the same meanings as in our Terms and Conditions.

Our Terms and Conditions (**“Terms”**) govern all use of our Service and together with the Privacy Policy constitutes your agreement with us (**“agreement”**).

1. **Definitions**

**SERVICE** means the reckonsoc.com website operated by Reckon.

**PERSONAL DATA** means data about a living individual who can be identified from those data (or from those and other information either in our possession or likely to come into our possession).

**USAGE DATA** is data collected automatically either generated by the use of Service or from Service infrastructure itself (for example, the duration of a page visit).

**COOKIES** are small files stored on your device (computer or mobile device).

**DATA CONTROLLER** means a natural or legal person who (either alone or jointly or in common with other persons) determines the purposes for which and the manner in which any personal data are, or are to be, processed. For the purpose of this Privacy Policy, we are a Data Controller of your data.

**DATA PROCESSORS (OR SERVICE PROVIDERS)** means any natural or legal person who processes the data on behalf of the Data Controller. We may use the services of various Service Providers in order to process your data more effectively.

**DATA SUBJECT** is any living individual who is the subject of Personal Data.

**THE USER** is the individual using our Service. The User corresponds to the Data Subject, who is the subject of Personal Data.

1. **Information Collection and Use**

We collect several different types of information for various purposes to provide and improve our Service to you.

1. **Types of Data Collected**

**Personal Data**

While using our Service, we may ask you to provide us with certain personally identifiable information that can be used to contact or identify you (**“Personal Data”**). Personally identifiable information may include, but is not limited to:

0.1. Email address

0.2. First name and last name

0.3. Phone number

0.4. Address, Country, State, Province, ZIP/Postal code, City

0.5. Cookies and Usage Data

We may use your Personal Data to contact you with newsletters, marketing or promotional materials and other information that may be of interest to you. You may opt out of receiving any, or all, of these communications from us by following the unsubscribe link.

**Usage Data**

We may also collect information that your browser sends whenever you visit our Service or when you access Service by or through any device (**“Usage Data”**).

This Usage Data may include information such as your computer’s Internet Protocol address (e.g. IP address), browser type, browser version, the pages of our Service that you visit, the time and date of your visit, the time spent on those pages, unique device identifiers and other diagnostic data.

When you access Service with a device, this Usage Data may include information such as the type of device you use, your device unique ID, the IP address of your device, your device operating system, the type of Internet browser you use, unique device identifiers and other diagnostic data.

**Tracking Cookies Data**

We use cookies and similar tracking technologies to track the activity on our Service and we hold certain information.

Cookies are files with a small amount of data which may include an anonymous unique identifier. Cookies are sent to your browser from a website and stored on your device. Other tracking technologies are also used such as beacons, tags and scripts to collect and track information and to improve and analyze our Service.

You can instruct your browser to refuse all cookies or to indicate when a cookie is being sent. However, if you do not accept cookies, you may not be able to use some portions of our Service.

Examples of Cookies we use:

0.1. **Session Cookies:** We use Session Cookies to operate our Service.

0.2. **Preference Cookies:** We use Preference Cookies to remember your preferences and various settings.

0.3. **Security Cookies:** We use Security Cookies for security purposes.

0.4. **Advertising Cookies:** Advertising Cookies are used to serve you with advertisements that may be relevant to you and your interests.


1. **Use of Data**

Reckon uses the collected data for various purposes:

0.1. to provide and maintain our Service;

0.2. to notify you about changes to our Service;

0.3. to allow you to participate in interactive features of our Service when you choose to do so;

0.4. to provide customer support;

0.5. to gather analysis or valuable information so that we can improve our Service;

0.6. to monitor the usage of our Service;

0.7. to detect, prevent and address technical issues;

0.8. to fulfill any other purpose for which you provide it;

0.9. to carry out our obligations and enforce our rights arising from any contracts entered into between you and us, including for billing and collection;

0.10. to provide you with notices about your account and/or subscription, including expiration and renewal notices, email-instructions, etc.;

0.11. to provide you with news, special offers and general information about other goods, services and events which we offer that are similar to those that you have already purchased or enquired about unless you have opted not to receive such information;

0.12. in any other way we may describe when you provide the information;

0.13. for any other purpose with your consent.

1. **Retention of Data**

We will retain your Personal Data only for as long as is necessary for the purposes set out in this Privacy Policy. We will retain and use your Personal Data to the extent necessary to comply with our legal obligations (for example, if we are required to retain your data to comply with applicable laws), resolve disputes, and enforce our legal agreements and policies.

We will also retain Usage Data for internal analysis purposes. Usage Data is generally retained for a shorter period, except when this data is used to strengthen the security or to improve the functionality of our Service, or we are legally obligated to retain this data for longer time periods.

1. **Transfer of Data**

Your information, including Personal Data, may be transferred to – and maintained on – computers located outside of your state, province, country or other governmental jurisdiction where the data protection laws may differ from those of your jurisdiction.

If you are located outside United States and choose to provide information to us, please note that we transfer the data, including Personal Data, to United States and process it there.

Your consent to this Privacy Policy followed by your submission of such information represents your agreement to that transfer.

Reckon will take all the steps reasonably necessary to ensure that your data is treated securely and in accordance with this Privacy Policy and no transfer of your Personal Data will take place to an organization or a country unless there are adequate controls in place including the security of your data and other personal information.

1. **Disclosure of Data**

We may disclose personal information that we collect, or you provide:

0.1. **Disclosure for Law Enforcement.**

Under certain circumstances, we may be required to disclose your Personal Data if required to do so by law or in response to valid requests by public authorities.

0.2. **Business Transaction.**

If we or our subsidiaries are involved in a merger, acquisition or asset sale, your Personal Data may be transferred.

0.3. **Other cases. We may disclose your information also:**

0.3.1. to our subsidiaries and affiliates;

0.3.2. to contractors, service providers, and other third parties we use to support our business;

0.3.3. to fulfill the purpose for which you provide it;

0.3.4. for the purpose of including your company’s logo on our website;

0.3.5. for any other purpose disclosed by us when you provide the information;

0.3.6. with your consent in any other cases;

0.3.7. if we believe disclosure is necessary or appropriate to protect the rights, property, or safety of the Company, our customers, or others.

1. **Security of Data**

The security of your data is important to us but remember that no method of transmission over the Internet or method of electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your Personal Data, we cannot guarantee its absolute security.

1. **Your Data Protection Rights Under General Data Protection Regulation (GDPR)**

If you are a resident of the European Union (EU) and European Economic Area (EEA), you have certain data protection rights, covered by GDPR.

We aim to take reasonable steps to allow you to correct, amend, delete, or limit the use of your Personal Data.

If you wish to be informed what Personal Data we hold about you and if you want it to be removed from our systems, please email us at **support@reckon.cc**.

In certain circumstances, you have the following data protection rights:

0.1. the right to access, update or to delete the information we have on you;

0.2. the right of rectification. You have the right to have your information rectified if that information is inaccurate or incomplete;

0.3. the right to object. You have the right to object to our processing of your Personal Data;

0.4. the right of restriction. You have the right to request that we restrict the processing of your personal information;

0.5. the right to data portability. You have the right to be provided with a copy of your Personal Data in a structured, machine-readable and commonly used format;

0.6. the right to withdraw consent. You also have the right to withdraw your consent at any time where we rely on your consent to process your personal information;

Please note that we may ask you to verify your identity before responding to such requests. Please note, we may not able to provide Service without some necessary data.

You have the right to complain to a Data Protection Authority about our collection and use of your Personal Data. For more information, please contact your local data protection authority in the European Economic Area (EEA).

1. **Your Data Protection Rights under the California Privacy Protection Act (CalOPPA)**

CalOPPA is the first state law in the nation to require commercial websites and online services to post a privacy policy. The law’s reach stretches well beyond California to require a person or company in the United States (and conceivable the world) that operates websites collecting personally identifiable information from California consumers to post a conspicuous privacy policy on its website stating exactly the information being collected and those individuals with whom it is being shared, and to comply with this policy.

According to CalOPPA we agree to the following:

0.1. users can visit our site anonymously;

0.2. our Privacy Policy link includes the word “Privacy”, and can easily be found on the home page of our website;

0.3. users will be notified of any privacy policy changes on our Privacy Policy Page;

0.4. users are able to change their personal information by emailing us at **support@reckon.cc**.

Our Policy on “Do Not Track” Signals:

We honor Do Not Track signals and do not track, plant cookies, or use advertising when a Do Not Track browser mechanism is in place. Do Not Track is a preference you can set in your web browser to inform websites that you do not want to be tracked.

You can enable or disable Do Not Track by visiting the Preferences or Settings page of your web browser.

1. **Your Data Protection Rights under the California Consumer Privacy Act (CCPA)**

If you are a California resident, you are entitled to learn what data we collect about you, ask to delete your data and not to sell (share) it. To exercise your data protection rights, you can make certain requests and ask us:

**0.1. What personal information we have about you. If you make this request, we will return to you:**

0.0.1. The categories of personal information we have collected about you.

0.0.2. The categories of sources from which we collect your personal information.

0.0.3. The business or commercial purpose for collecting or selling your personal information.

0.0.4. The categories of third parties with whom we share personal information.

0.0.5. The specific pieces of personal information we have collected about you.

0.0.6. A list of categories of personal information that we have sold, along with the category of any other company we sold it to. If we have not sold your personal information, we will inform you of that fact.

0.0.7. A list of categories of personal information that we have disclosed for a business purpose, along with the category of any other company we shared it with.

Please note, you are entitled to ask us to provide you with this information up to two times in a rolling twelve-month period. When you make this request, the information provided may be limited to the personal information we collected about you in the previous 12 months.

**0.2. To delete your personal information. If you make this request, we will delete the personal information we hold about you as of the date of your request from our records and direct any service providers to do the same. In some cases, deletion may be accomplished through de-identification of the information. If you choose to delete your personal information, you may not be able to use certain functions that require your personal information to operate.**

**0.3. To stop selling your personal information. We don’t sell or rent your personal information to any third parties for any purpose. We do not sell your personal information for monetary consideration. However, under some circumstances, a transfer of personal information to a third party, or within our family of companies, without monetary consideration may be considered a “sale” under California law. You are the only owner of your Personal Data and can request disclosure or deletion at any time.**

If you submit a request to stop selling your personal information, we will stop making such transfers.

Please note, if you ask us to delete or stop selling your data, it may impact your experience with us, and you may not be able to participate in certain programs or membership services which require the usage of your personal information to function. But in no circumstances, we will discriminate against you for exercising your rights.

To exercise your California data protection rights described above, please send your request(s) by email: **support@reckon.cc**.

Your data protection rights, described above, are covered by the CCPA, short for the California Consumer Privacy Act. To find out more, visit the official California Legislative Information website. The CCPA took effect on 01/01/2020.

1. **Service Providers**

We may employ third party companies and individuals to facilitate our Service (**“Service Providers”**), provide Service on our behalf, perform Service-related services or assist us in analysing how our Service is used.

These third parties have access to your Personal Data only to perform these tasks on our behalf and are obligated not to disclose or use it for any other purpose.

1. **Analytics**

We may use third-party Service Providers to monitor and analyze the use of our Service.

1. **CI/CD tools**

We may use third-party Service Providers to automate the development process of our Service.

1. **Behavioral Remarketing**

We may use remarketing services to advertise on third party websites to you after you visited our Service. We and our third-party vendors use cookies to inform, optimise and serve ads based on your past visits to our Service.

1. **Links to Other Sites**

Our Service may contain links to other sites that are not operated by us. If you click a third party link, you will be directed to that third party’s site. We strongly advise you to review the Privacy Policy of every site you visit.

We have no control over and assume no responsibility for the content, privacy policies or practices of any third party sites or services.

1. **Children’s Privacy**

Our Services are not intended for use by children under the age of 18 (**“Child”** or **“Children”**).

We do not knowingly collect personally identifiable information from Children under 18. If you become aware that a Child has provided us with Personal Data, please contact us. If we become aware that we have collected Personal Data from Children without verification of parental consent, we take steps to remove that information from our servers.

1. **Changes to This Privacy Policy**

We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page.

We will let you know via email and/or a prominent notice on our Service, prior to the change becoming effective and update “effective date” at the top of this Privacy Policy.

You are advised to review this Privacy Policy periodically for any changes. Changes to this Privacy Policy are effective when they are posted on this page.

1. **Contact Us**

If you have any questions about this Privacy Policy, please contact us by email: **support@reckon.cc**.

"""

@rx.page(on_load=AppState.check_login(), **page_params)
def privacy():
    """The privacy page."""
    return info_page(privacy_text)

