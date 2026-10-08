import type { CompletedCase } from '../types'

// DEMO DATA — anonymised, synthetic case records contributed by lawyers.
// These are NOT real judgments and must never be cited as authority.
export const seedCompletedCases: CompletedCase[] = [
  {
    id: 'FLC-2201', lawyerId: 'LAW-101', title: 'State v. R.S. (anonymised)', area: 'Criminal', court: 'Delhi High Court', year: 2025,
    outcome: 'Bail granted', sections: ['BNSS s.483', 'Art. 21', 'Art. 22(2)'],
    summary: 'Regular bail granted after the defence showed the accused was not produced before a magistrate within 24 hours and the arrest memo carried an inconsistent date.',
    keywords: ['bail', 'arrest', 'remand', 'arrest memo', 'magistrate', '24 hours', 'date', 'inconsistent', 'custody'], durationMonths: 2, verified: true,
  },
  {
    id: 'FLC-2202', lawyerId: 'LAW-102', title: 'State v. A.P. (anonymised)', area: 'Criminal', court: 'Sessions Court, Mumbai', year: 2024,
    outcome: 'Acquitted', sections: ['BNS s.303', 'BSA s.63'],
    summary: 'Acquittal in a theft prosecution after CCTV and attendance records established that the accused was elsewhere at the time of the alleged offence.',
    keywords: ['theft', 'alibi', 'attendance', 'cctv', 'witness', 'employment', 'record', 'fir'], durationMonths: 14, verified: true,
  },
  {
    id: 'FLC-2203', lawyerId: 'LAW-108', title: 'State v. M.K. (anonymised)', area: 'Criminal', court: 'Rajasthan High Court', year: 2025,
    outcome: 'Bail granted', sections: ['BNSS s.480', 'BNSS s.58'],
    summary: 'Bail granted where the remand application and the FIR narrative recorded different arrest times and no previous bail history was placed on record.',
    keywords: ['bail', 'remand', 'fir', 'arrest', 'previous bail', 'witness', 'contradiction'], durationMonths: 1, verified: true,
  },
  {
    id: 'FLC-2204', lawyerId: 'LAW-110', title: 'In re Habeas Corpus — S.Y. (anonymised)', area: 'Constitutional', court: 'Allahabad High Court', year: 2023,
    outcome: 'Allowed', sections: ['Art. 21', 'Art. 22', 'Art. 226'],
    summary: 'Habeas corpus allowed; detention found unlawful because grounds of arrest were not communicated in writing.',
    keywords: ['habeas corpus', 'detention', 'arrest', 'grounds', 'custody', 'writ'], durationMonths: 3, verified: true,
  },
  {
    id: 'FLC-2205', lawyerId: 'LAW-103', title: 'P.R. v. K.R. (anonymised)', area: 'Family', court: 'Family Court, Hyderabad', year: 2024,
    outcome: 'Settled', sections: ['HMA s.13B', 'BNSS s.144'],
    summary: 'Mutual-consent divorce with a negotiated lump-sum maintenance and shared custody schedule after two mediation sessions.',
    keywords: ['divorce', 'maintenance', 'custody', 'mediation', 'marriage', 'child'], durationMonths: 7, verified: true,
  },
  {
    id: 'FLC-2206', lawyerId: 'LAW-103', title: 'N.S. v. A.S. (anonymised)', area: 'Family', court: 'Family Court, Hyderabad', year: 2025,
    outcome: 'Decree passed', sections: ['PWDVA s.12', 'BNSS s.144'],
    summary: 'Protection and residence orders under the Domestic Violence Act along with interim maintenance.',
    keywords: ['domestic violence', 'maintenance', 'residence', 'protection order', 'marriage'], durationMonths: 9, verified: true,
  },
  {
    id: 'FLC-2207', lawyerId: 'LAW-105', title: 'H.S. v. J.S. & Ors. (anonymised)', area: 'Property', court: 'Punjab & Haryana High Court', year: 2024,
    outcome: 'Decree passed', sections: ['CPC O.XX R.18', 'Hindu Succession Act s.6'],
    summary: 'Partition decree recognising a daughter’s coparcenary share in ancestral agricultural land.',
    keywords: ['partition', 'ancestral', 'land', 'succession', 'coparcenary', 'property', 'title'], durationMonths: 22, verified: true,
  },
  {
    id: 'FLC-2208', lawyerId: 'LAW-108', title: 'G.L. v. Tehsildar (anonymised)', area: 'Property', court: 'Rajasthan High Court', year: 2023,
    outcome: 'Allowed', sections: ['Art. 226', 'Rajasthan Land Revenue Act'],
    summary: 'Mutation entry restored after the authority acted without notice to the recorded owner.',
    keywords: ['mutation', 'land', 'revenue', 'notice', 'property', 'title'], durationMonths: 6, verified: true,
  },
  {
    id: 'FLC-2209', lawyerId: 'LAW-107', title: 'R.M. v. E-commerce Platform (anonymised)', area: 'Consumer', court: 'District Consumer Commission, Bengaluru', year: 2025,
    outcome: 'Allowed', sections: ['CPA 2019 s.35', 'CPA 2019 s.2(47)'],
    summary: 'Refund plus compensation ordered for a defective smartphone and refusal to honour warranty.',
    keywords: ['refund', 'defective', 'warranty', 'e-commerce', 'consumer', 'compensation', 'deficiency'], durationMonths: 5, verified: true,
  },
  {
    id: 'FLC-2210', lawyerId: 'LAW-107', title: 'State v. Unknown (UPI fraud, anonymised)', area: 'Cyber', court: 'Cyber Police / Karnataka High Court', year: 2025,
    outcome: 'Allowed', sections: ['IT Act s.66D', 'BNS s.318'],
    summary: 'Directions to the bank to freeze and restore funds lost in a UPI phishing fraud after timely complaint on the national cybercrime portal.',
    keywords: ['upi', 'fraud', 'phishing', 'bank', 'cyber', 'online', 'otp'], durationMonths: 4, verified: true,
  },
  {
    id: 'FLC-2211', lawyerId: 'LAW-102', title: 'State v. D.T. (anonymised)', area: 'Cyber', court: 'Sessions Court, Mumbai', year: 2024,
    outcome: 'Bail granted', sections: ['IT Act s.66C', 'BNSS s.480'],
    summary: 'Bail in an identity-theft case where digital evidence was not accompanied by the required electronic-record certificate.',
    keywords: ['identity theft', 'digital evidence', 'certificate', 'bail', 'cyber', 'arrest'], durationMonths: 2, verified: true,
  },
  {
    id: 'FLC-2212', lawyerId: 'LAW-104', title: 'Vendor v. Tech Pvt. Ltd. (anonymised)', area: 'Corporate', court: 'Arbitral Tribunal, Chennai', year: 2024,
    outcome: 'Settled', sections: ['Arbitration Act s.9', 'Indian Contract Act s.73'],
    summary: 'Settlement of unpaid invoices after interim protection; uncapped liability clause renegotiated.',
    keywords: ['contract', 'invoice', 'liability', 'indemnity', 'arbitration', 'breach', 'termination'], durationMonths: 8, verified: true,
  },
  {
    id: 'FLC-2213', lawyerId: 'LAW-109', title: 'Employee v. Logistics Co. (anonymised)', area: 'Labour', court: 'Labour Court, Pune', year: 2025,
    outcome: 'Allowed', sections: ['Industrial Disputes Act s.25F', 'Payment of Gratuity Act'],
    summary: 'Reinstatement with 50% back wages after retrenchment without notice or compensation.',
    keywords: ['termination', 'retrenchment', 'wages', 'gratuity', 'employment', 'notice', 'salary'], durationMonths: 11, verified: true,
  },
  {
    id: 'FLC-2214', lawyerId: 'LAW-106', title: 'Infra JV Arbitration (anonymised)', area: 'Corporate', court: 'Sole Arbitrator', year: 2023,
    outcome: 'Decree passed', sections: ['Arbitration Act s.31'],
    summary: 'Award on delay damages in an EPC contract with a liquidated-damages cap applied.',
    keywords: ['contract', 'delay', 'damages', 'arbitration', 'liability'], durationMonths: 15, verified: true,
  },
]
