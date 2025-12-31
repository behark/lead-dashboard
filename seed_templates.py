"""
Seed database with category-specific message templates
"""
from app import create_app
from models import db, MessageTemplate, ContactChannel, Sequence, SequenceStep


def create_templates():
    """Create category-specific message templates"""
    
    templates = [
        # DENTIST
        {
            'name': 'Dentist - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'dentist',
            'content': '''Pershendetje 👋

Pashe {business_name} ne Google - {rating}⭐ shkelqyeshem!
Urime per kaq shume paciente te kenaqur 👏

Pyetje e shpejte: A po humbni paciente sepse nuk mund te rezervojne online?

Shumica e dentisteve me thone se po humbin rezervime pas orarit. Dikush do te rezervoje ne oren 21:00 - nuk mundet, shkon te konkurrenti.

Une ndihmoj klinikat dentare te shtojne rezervime online.
Zakonisht dentistet shohin 10-15 rezervime te reja/muaj vetem nga rezervimet online.

A do te flisnit 5 minuta per kete?''',
            'variant': 'A'
        },
        
        # RESTAURANT
        {
            'name': 'Restaurant - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'restaurant',
            'content': '''Pershendetje 👋

Kontrollova {business_name} ne Google - {rating}⭐ dhe komentet duken shkelqyeshem!
Ushqimi duhet te jete i shijshem 🍽️

Pyetje: A po humbni kliente sepse nuk mund te gjejne menune online?

Ja cfare ndodh: Dikush kerkon "restorant {city}" ne Google, ju gjen, klikon... dhe ska menu, ska mundesi te porosise. Iken.

Restorantet me menu online + porosi shohin 20-30% me shume te ardhura.

A do te flisnit shkurt per kete?''',
            'variant': 'A'
        },
        
        # SALON / BARBERSHOP
        {
            'name': 'Salon - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'salon',
            'content': '''Pershendetje 👋

Pashe {business_name} ne Google - {rating}⭐, po beni shkelqyeshem!
Shume kliente te kenaqur 💇‍♀️

Pyetje e shpejte: Sa kohe kaloni cdo dite duke u pergjigjur telefonatave per rezervime?

Shumica e salloneve me thone 1-2 ore/dite ne telefon.
Me nje sistem rezervimi online, kjo bie ne 15 minuta - dhe merrni ME SHUME rezervime.

Plus, klientet pelqejne te rezervojne ne mengjes pa telefonuar gjate oreve tuaja te ngarkuara.

A jeni te interesuar per nje bisede 5-minuteshe?''',
            'variant': 'A'
        },
        {
            'name': 'Barber - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'barber',
            'content': '''Pershendetje 👋

Pashe {business_name} ne Google - {rating}⭐, shkelqyeshem!
Shume kliente te kenaqur 💈

Pyetje: Sa telefonata rezervimi merrni pas orarit te punes?

Me nje sistem rezervimi online, klientet mund te rezervojne 24/7 - edhe ne mengjes.
Barberet qe perdorin kete zakonisht marrin 15-20 rezervime me shume/muaj.

A do te flisnit 5 minuta?''',
            'variant': 'A'
        },
        
        # LAWYER
        {
            'name': 'Lawyer - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'lawyer',
            'content': '''Pershendetje 👋

Gjeta {business_name} - {rating}⭐ me komente solide.

Vezhgim i shpejte: Kur dikush ne {city} kerkon "avokat divorci" ose "avokat biznesi", a dilni ne faqen e pare te Google?

Shumica e avokateve me thone "jo vertet" ose "jo gjithmone".

Ky eshte problem sepse 80% e njerezve nuk kalojne faqen 1 te Google.
Pra po humbni kliente qe jane duke kerkuar PIKËRISHT per JU.

Une ndihmoj firmat ligjore te kene dukshmeri me te mire ne Google.
Avokatet me te cilet punoj zakonisht marrin 2-4 kerkesa te reja/muaj vetem nga dukshmeria ne Google.

A do te flisnit 5 minuta per kete?''',
            'variant': 'A'
        },
        
        # CAR REPAIR
        {
            'name': 'Car Repair - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'car repair',
            'content': '''Pershendetje 👋

Pashe {business_name} ne Google - {rating}⭐, qartazi i besueshem nga klientet tuaj!

Pyetje: Sa kliente humbni sepse nuk mund te rezervojne riparim online?

Ja cfare dua te them: Makina e dikujt prishet, kerkon "riparim makine afer {city}", ju gjen, do te rezervoje... por duhet te telefonoje ose te vije personalisht.
Shume thjesht zgjedhin cilin mund ta kontaktojne me lehte.

Auto-serviset me rezervim online zakonisht shohin 15-20 rezervime me shume/muaj.

A jeni te interesuar te flisni 5 minuta per shtimin e kesaj?''',
            'variant': 'A'
        },
        
        # GYM
        {
            'name': 'Gym - Initial (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': 'gym',
            'content': '''Pershendetje 👋

Kontrollova {business_name} ne Google - {rating}⭐ duket shkelqyeshem!

Pyetje e shpejte: Sa e lehte eshte per dikë te regjistrohet per anetaresim online?

Shumica e palestrave me thone: "Duhet te vijne personalisht" ose "Na telefononi per te filluar."

Kjo po ju humb anetare. Njerezit duan te regjistrohen ne oren 23:00 nga telefoni i tyre.

Palestrat me anetaresim online + sistem pagese zakonisht shohin 30-40% me shume regjistrime.

Te interesuar per nje bisede te shpejte?''',
            'variant': 'A'
        },
        
        # FOLLOW-UP TEMPLATES
        {
            'name': 'Follow-up Day 1 (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': None,
            'content': '''Pershendetje 👋

Po ndjek mesazhin tim per {business_name}.

Pa presion - thjesht doja te shoh nese jeni te interesuar te flisni?

Gjithe te mirat!''',
            'variant': 'A'
        },
        {
            'name': 'Follow-up Day 2 - Reframe (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': None,
            'content': '''Pershendetje,

Pyetje e shpejte: Sa kliente humbni sepse nuk mund t'ju gjejne online?

Ndoshta shume pa e ditur.

Nje uebsajt i thjeshte e zgjidh kete.

Te flasim?''',
            'variant': 'A'
        },
        {
            'name': 'Follow-up Day 3 - Portfolio (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': None,
            'content': '''Pershendetje,

Doja t'ju tregoj dicka.

Muajin e kaluar ndertova nje uebsajt per nje biznes te ngjashem me tuajin.

Rezultati: 15 kliente te rinj ate muaj qe nuk do t'i kishin marre.

Nese doni te njejten per {business_name}, mund ta bej brenda 5-7 diteve.

Te interesuar?''',
            'variant': 'A'
        },
        {
            'name': 'Follow-up Day 5 - Final (Albanian)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'sq',
            'category': None,
            'content': '''Pershendetje,

Ky eshte mesazhi im i fundit.

Nese ndonjehere vendosni qe doni ndihme me nje uebsajt per {business_name}, dini ku te me gjeni.

Ju uroj sukses! 🙏''',
            'variant': 'A'
        },
        
        # ENGLISH VERSIONS
        {
            'name': 'Generic - Initial (English)',
            'channel': ContactChannel.WHATSAPP,
            'language': 'en',
            'category': None,
            'content': '''Hi 👋

I came across {business_name} on Google - {rating}⭐ is impressive!
Congrats on having so many satisfied customers 👏

Quick question: Are you losing customers because they can't find you online?

I help local businesses get simple, professional websites that bring more customers.

Would you be open to a quick 5-min chat?''',
            'variant': 'A'
        },
    ]
    
    app = create_app()
    
    with app.app_context():
        created = 0
        for t in templates:
            if not MessageTemplate.query.filter_by(name=t['name']).first():
                template = MessageTemplate(**t)
                db.session.add(template)
                created += 1
                print(f"Created: {t['name']}")
        
        db.session.commit()
        print(f"\nCreated {created} templates")
        
        # Create default sequence
        if not Sequence.query.filter_by(name='5-Step Follow-up').first():
            seq = Sequence(
                name='5-Step Follow-up',
                description='Day 0: Initial → Day 1: Gentle → Day 2: Reframe → Day 3: Portfolio → Day 5: Final'
            )
            db.session.add(seq)
            db.session.flush()
            
            # Get follow-up templates
            day1_t = MessageTemplate.query.filter_by(name='Follow-up Day 1 (Albanian)').first()
            day2_t = MessageTemplate.query.filter_by(name='Follow-up Day 2 - Reframe (Albanian)').first()
            day3_t = MessageTemplate.query.filter_by(name='Follow-up Day 3 - Portfolio (Albanian)').first()
            day5_t = MessageTemplate.query.filter_by(name='Follow-up Day 5 - Final (Albanian)').first()
            
            steps = [
                SequenceStep(sequence_id=seq.id, step_number=1, channel=ContactChannel.WHATSAPP, 
                            template_id=day1_t.id if day1_t else None, delay_days=1),
                SequenceStep(sequence_id=seq.id, step_number=2, channel=ContactChannel.WHATSAPP,
                            template_id=day2_t.id if day2_t else None, delay_days=1),
                SequenceStep(sequence_id=seq.id, step_number=3, channel=ContactChannel.WHATSAPP,
                            template_id=day3_t.id if day3_t else None, delay_days=1),
                SequenceStep(sequence_id=seq.id, step_number=4, channel=ContactChannel.WHATSAPP,
                            template_id=day5_t.id if day5_t else None, delay_days=2),
            ]
            
            for step in steps:
                db.session.add(step)
            
            db.session.commit()
            print("Created 5-Step Follow-up sequence")


if __name__ == '__main__':
    create_templates()
