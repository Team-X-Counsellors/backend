"""
Generate the JaliMind self-help workbooks as PDFs into the frontend's public/workbooks folder
(Netlify serves them; Railway's disk is ephemeral so uploads there would vanish on redeploy).

    pip install reportlab      # dev-only, not a runtime requirement
    python scripts/make_workbooks.py

These are self-help exercises based on widely used CBT / behavioural techniques. They are not
treatment, and every workbook says so and points to a counsellor and crisis lines.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

OUT = Path(__file__).resolve().parents[2] / 'JaliMind' / 'public' / 'workbooks'
INDIGO, NIGHT, MARIGOLD, LILAC = colors.HexColor('#3D35C4'), colors.HexColor('#17163B'), colors.HexColor('#FFB224'), colors.HexColor('#ECE9FF')

base = getSampleStyleSheet()
H1 = ParagraphStyle('H1', parent=base['Title'], fontName='Helvetica-Bold', fontSize=26, leading=30, textColor=NIGHT, alignment=0, spaceAfter=6)
H2 = ParagraphStyle('H2', parent=base['Heading2'], fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=INDIGO, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle('Body', parent=base['BodyText'], fontName='Helvetica', fontSize=11, leading=16, textColor=NIGHT)
SMALL = ParagraphStyle('Small', parent=BODY, fontSize=9, leading=13, textColor=colors.HexColor('#5C5A80'))

CRISIS = ('If you are in danger or thinking about hurting yourself, contact someone now: Kenya, Befrienders Kenya +254 722 178 177 · '
          'Nigeria, SURPIN +234 806 210 6493 · Ghana, Mental Health Authority 0800 111 222 · South Africa, SADAG 0800 456 789. '
          'Or go to your university counselling centre.')


def lines(n=3):
    return Table([[''] for _ in range(n)], colWidths=[170 * mm], rowHeights=[9 * mm] * n,
                 style=TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#B9B5E8'))]))


def box(text):
    t = Table([[Paragraph(text, BODY)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), LILAC), ('BOX', (0, 0), (-1, -1), 0, LILAC),
                           ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                           ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    return t


def prompt(label, n=3):
    return [Paragraph(label, BODY), Spacer(1, 2), lines(n), Spacer(1, 6)]


def table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#B9B5E8')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('FONTSIZE', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), INDIGO), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
               ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')]
    t.setStyle(TableStyle(st))
    return t


def header(title, sub):
    return [Paragraph('JaliMind', ParagraphStyle('b', parent=SMALL, textColor=INDIGO, fontName='Helvetica-Bold')),
            Spacer(1, 8), Paragraph(title, H1), Paragraph(sub, BODY), Spacer(1, 6),
            HRFlowable(width='100%', thickness=3, color=MARIGOLD, spaceAfter=10)]


def footer(story):
    story += [Spacer(1, 14), HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#B9B5E8')), Spacer(1, 6),
              Paragraph('This workbook is self-help, not treatment or a diagnosis. A counsellor on JaliMind can go through it with you.', SMALL),
              Spacer(1, 3), Paragraph(CRISIS, SMALL)]


def build(filename, title, sub, content):
    OUT.mkdir(parents=True, exist_ok=True)
    story = header(title, sub) + content
    footer(story)
    SimpleDocTemplate(str(OUT / filename), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                      bottomMargin=18 * mm, title=title, author='JaliMind').build(story)
    print('wrote', OUT / filename)


def exam():
    c = [Paragraph('1. Name what is worrying you', H2), *prompt('Which exam or deadline is on your mind most? What exactly are you afraid will happen?', 3),
         Paragraph('2. Two-week plan', H2),
         table([['Subject / task', 'Date', 'Small step for this week', 'Done'], *[['', '', '', ''] for _ in range(6)]], [50 * mm, 25 * mm, 80 * mm, 15 * mm]),
         Spacer(1, 6), box('Study in blocks of 25 minutes, then rest for 5. Four blocks, then a 20-minute break. Rest is part of studying.'),
         PageBreak(), Paragraph('3. Catch the anxious thought', H2),
         table([['The thought', 'How true is it? (0-100)', 'A fairer thought'], ['"I will fail everything."', '', '"I have passed hard things before. I can prepare for this one."'], *[['', '', ''] for _ in range(4)]], [60 * mm, 35 * mm, 75 * mm]),
         Paragraph('4. Reset when you feel panic rising', H2),
         Paragraph('<b>Box breathing:</b> breathe in for 4, hold for 4, out for 4, hold for 4. Repeat 4 times.<br/>'
                   '<b>5-4-3-2-1:</b> name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste.<br/>'
                   '<b>Move:</b> a 10-minute walk lowers stress better than another hour of panic-reading.', BODY),
         Paragraph('5. Exam-day basics', H2),
         table([['Night before', 'Morning of', 'Afterwards'], ['Pack your things\nSleep, even if short\nNo new topics', 'Eat something\nArrive early\nBreathe before you start', 'Do not replay it\nRest\nTalk to someone']], [57 * mm] * 3),
         Paragraph('6. Who can help', H2), *prompt('Write down two people you can message this week, and one thing you will ask them for.', 3)]
    build('exam-season-survival-workbook.pdf', 'Exam Season Survival Workbook', 'A calm plan for the weeks before exams. About 30 minutes.', c)


def identity():
    c = [Paragraph('1. What matters to you', H2), Paragraph('Circle the five values that feel most like you, then rank them.', BODY), Spacer(1, 4),
         box('Family · Faith · Honesty · Learning · Freedom · Community · Kindness · Success · Courage · Creativity · Respect · Humour · Independence · Service · Peace'),
         Spacer(1, 6), *prompt('My top three, in order, and why:', 3),
         Paragraph('2. Where you come from', H2), *prompt('What from your family, culture or community are you proud of?', 3),
         *prompt('What expectations do you carry that feel heavy?', 3), PageBreak(),
         Paragraph('3. Two worlds', H2), Paragraph('Many students move between home and campus, between languages, between who others expect and who they are.', BODY), Spacer(1, 4),
         table([['At home I am...', 'On campus I am...'], *[['', ''] for _ in range(5)]], [85 * mm, 85 * mm]),
         Spacer(1, 6), *prompt('What parts of me are the same in both places?', 3),
         Paragraph('4. A conversation I need to have', H2), *prompt('Who? What is the one thing I want them to understand? What will I say first?', 4),
         Paragraph('5. One small step this week', H2), *prompt('Something that lets me act on my top value:', 2)]
    build('identity-workbook.pdf', 'The Identity Workbook', 'Culture, family and self. Find what is yours, and what you want to keep.', c)


def sleep():
    rows = [['Day', 'Today I will', 'Bedtime', 'Woke at', 'Rested? 1-5']]
    plan = ['Same wake-up time every day, even on weekends', 'No caffeine after 2pm', 'Phone away 30 minutes before bed',
            'Move your body for 20 minutes', 'Write tomorrow\'s worries on paper before bed', 'Cool, dark, quiet room', 'Review: keep what worked']
    for i, p in enumerate(plan, 1):
        rows.append([f'Day {i}', p, '', '', ''])
    c = [Paragraph('Your 7-day plan', H2), table(rows, [18 * mm, 78 * mm, 24 * mm, 24 * mm, 26 * mm]),
         Spacer(1, 8), box('Cannot sleep after 20 minutes? Get up, sit somewhere dim, do something boring, and go back when sleepy. Lying there frustrated teaches your brain that bed means stress.'),
         Paragraph('Worry list (do this before bed)', H2), *prompt('What is on my mind, and what is one thing I can do about it tomorrow?', 4),
         Paragraph('What I noticed', H2), *prompt('Which habits helped most? Which will I keep?', 3),
         Paragraph('When to get help', H2), Paragraph('If poor sleep lasts more than a few weeks, comes with low mood or constant worry, or gets in the way of your studies, talk to a counsellor.', BODY)]
    build('sleep-reset-7-day-plan.pdf', 'Sleep Reset: a 7-Day Plan', 'Small changes that add up. One a day.', c)


def safety():
    steps = [('1. My warning signs', 'Thoughts, moods or situations that tell me a crisis may be starting:'),
             ('2. Things I can do on my own', 'Walk, breathing, music, a shower, prayer or meditation, a game:'),
             ('3. People and places that help me feel better', 'Names, or places where being around others helps:'),
             ('4. People I can ask for help', 'Name and phone number:'),
             ('5. Professionals and crisis lines', 'My counsellor, university centre, and the numbers below:'),
             ('6. Making my space safer', 'Things I can put out of reach or ask someone to hold for me:')]
    c = [Paragraph('Fill this in when you are feeling okay, so it is ready when you are not. Keep a photo of it on your phone.', BODY), Spacer(1, 6)]
    for t, p in steps:
        c += [Paragraph(t, H2), *prompt(p, 2)]
    c += [box('<b>One reason to keep going:</b> ______________________________________________')]
    build('my-safety-plan.pdf', 'My Safety Plan', 'A short plan for the hardest moments. Based on the Stanley-Brown safety planning approach.', c)


if __name__ == '__main__':
    exam(); identity(); sleep(); safety()
