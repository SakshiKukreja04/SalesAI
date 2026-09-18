import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Neo4j retrieval tests
# ---------------------------------------------------------------------------
from app.neo4j_retrieval import format_graph_context, get_customer_context, get_salesai_context


class TestNeo4jRetrieval(unittest.TestCase):

    def _make_row(self, **overrides):
        base = {
            'customer_id': 'c-1',
            'customer_name': 'Alice Johnson',
            'customer_email': 'alice@example.com',
            'customer_tier': 'gold',
            'customer_status': 'active',
            'order_id': 'o-1',
            'order_number': 'SFX-001',
            'order_status': 'delivered',
            'order_date': '2026-08-15',
            'total_amount': 2499,
            'product_name': 'TechNova Laptop Stand',
            'sku': 'LS-003',
            'quantity': 1,
            'unit_price': 2499,
            'shipment_status': 'delivered',
            'carrier': 'BlueDart',
            'shipped_at': '2026-08-16',
            'tracking_number': 'BD-TRK-789',
            'estimated_delivery': '2026-08-20',
            'delivered_at': '2026-08-19',
        }
        base.update(overrides)
        return base

    def test_unknown_customer_returns_empty_context(self):
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = []
            result = get_salesai_context('ghost@nowhere.com')
        self.assertFalse(result['customer_found'])
        self.assertIsNone(result['customer'])
        self.assertEqual(result['orders'], [])

    def test_unconfigured_neo4j_returns_default(self):
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = False
            result = get_salesai_context('any@example.com')
        self.assertFalse(result['customer_found'])

    def test_full_customer_context_parsed(self):
        row = self._make_row()
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = [row]
            ctx = get_customer_context('alice@example.com')
        self.assertTrue(ctx['customer_found'])
        self.assertEqual(ctx['customer']['name'], 'Alice Johnson')
        self.assertEqual(ctx['customer']['tier'], 'gold')
        self.assertEqual(len(ctx['orders']), 1)
        self.assertEqual(ctx['orders'][0]['products'][0]['sku'], 'LS-003')

    def test_email_lookup_is_case_insensitive(self):
        row = self._make_row()
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = [row]
            ctx = get_customer_context('ALICE@EXAMPLE.COM')
        self.assertTrue(ctx['customer_found'])

    def test_multiple_products_aggregated_per_order(self):
        row1 = self._make_row(product_name='Jacket', sku='JK-01', quantity=1, unit_price=999)
        row2 = self._make_row(product_name='Running Shoes', sku='RS-02', quantity=2, unit_price=1499)
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = [row1, row2]
            ctx = get_customer_context('alice@example.com')
        self.assertEqual(len(ctx['orders']), 1)
        self.assertEqual(len(ctx['orders'][0]['products']), 2)

    def test_format_graph_context_includes_order_details(self):
        row = self._make_row()
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = [row]
            ctx = get_customer_context('alice@example.com')
        formatted = format_graph_context({**ctx, 'previous_conversations': [], 'issues': [], 'interests': []})
        self.assertIn('Order SFX-001', formatted)
        self.assertIn('gold', formatted)
        self.assertIn('BD-TRK-789', formatted)

    def test_customer_with_no_orders(self):
        row = self._make_row(order_id=None, order_number=None, product_name=None)
        with patch('app.neo4j_retrieval.neo4j_client') as client:
            client.configured = True
            client.read_records.return_value = [row]
            ctx = get_customer_context('alice@example.com')
        self.assertTrue(ctx['customer_found'])
        self.assertEqual(ctx['orders'], [])

    def test_format_graph_context_empty_returns_empty_string(self):
        result = format_graph_context({'customer_found': False, 'customer': None, 'orders': []})
        self.assertEqual(result, '')

    def test_empty_email_returns_not_found(self):
        result = get_customer_context('')
        self.assertFalse(result['customer_found'])

    def test_whitespace_email_returns_not_found(self):
        result = get_customer_context('   ')
        self.assertFalse(result['customer_found'])


# ---------------------------------------------------------------------------
# Sentiment, Risk, Repeat issue tests
# ---------------------------------------------------------------------------
from app.memory.memory_retriever import (
    _calculate_risk_level,
    _calculate_sentiment_trend,
    _detect_repeat_issues,
)
from app.memory.memory_models import ConversationRecord, CustomerIssue


class TestSentimentTrend(unittest.TestCase):

    def _conv(self, emotion):
        return ConversationRecord(emotion=emotion)

    def test_empty_is_zero(self):
        self.assertEqual(_calculate_sentiment_trend([]), 0.0)

    def test_happy_is_positive(self):
        self.assertGreater(_calculate_sentiment_trend([self._conv('happy')]), 0)

    def test_angry_is_negative(self):
        self.assertLess(_calculate_sentiment_trend([self._conv('angry')]), 0)

    def test_all_angry_very_negative(self):
        convs = [self._conv('angry')] * 6
        self.assertLess(_calculate_sentiment_trend(convs), -0.5)

    def test_result_clamped(self):
        convs = [self._conv('angry')] * 10
        r = _calculate_sentiment_trend(convs)
        self.assertGreaterEqual(r, -1.0)
        self.assertLessEqual(r, 1.0)


class TestRiskLevel(unittest.TestCase):

    def _issue(self, priority='medium'):
        return CustomerIssue(issue_title='Test', priority=priority, status='open')

    def test_low_risk_default(self):
        self.assertEqual(_calculate_risk_level([], [], 0.0, 'neutral', False), 'LOW')

    def test_open_issue_is_high(self):
        self.assertEqual(_calculate_risk_level([self._issue()], [], 0.0, 'neutral', False), 'HIGH')

    def test_angry_is_high(self):
        self.assertEqual(_calculate_risk_level([], [], 0.0, 'angry', False), 'HIGH')

    def test_repeat_issue_is_high(self):
        self.assertEqual(_calculate_risk_level([], [], 0.0, 'neutral', True), 'HIGH')

    def test_two_issues_plus_angry_escalates(self):
        self.assertEqual(_calculate_risk_level([self._issue(), self._issue()], [], -0.5, 'angry', True), 'ESCALATE_IMMEDIATELY')

    def test_frustrated_is_medium(self):
        self.assertEqual(_calculate_risk_level([], [], 0.0, 'frustrated', False), 'MEDIUM')


class TestRepeatIssueDetection(unittest.TestCase):

    def _issue(self, title):
        return CustomerIssue(issue_title=title)

    def _conv(self, intent):
        return ConversationRecord(intent=intent)

    def test_empty_intent_is_false(self):
        found, _ = _detect_repeat_issues('', [], [])
        self.assertFalse(found)

    def test_open_issue_match(self):
        found, label = _detect_repeat_issues('refund_request', [self._issue('Refund request for jacket')], [])
        self.assertTrue(found)

    def test_repeated_intent_flagged(self):
        convs = [self._conv('order_status'), self._conv('order_status')]
        found, label = _detect_repeat_issues('order_status', [], convs)
        self.assertTrue(found)

    def test_single_occurrence_not_flagged(self):
        convs = [self._conv('order_status')]
        found, _ = _detect_repeat_issues('order_status', [], convs)
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# Memory formatter
# ---------------------------------------------------------------------------
from app.memory.memory_formatter import format_customer_memory
from app.memory.memory_models import CustomerMemory, CustomerProfile


class TestMemoryFormatter(unittest.TestCase):

    def _profile(self, name='Alice', interactions=3):
        return CustomerProfile(customer_id='uuid-1', email='alice@example.com', name=name, total_interactions=interactions)

    def test_new_customer_label(self):
        memory = CustomerMemory(is_empty=True)
        self.assertIn('NEW CUSTOMER', format_customer_memory(memory).full_context_text)

    def test_existing_customer_has_profile(self):
        memory = CustomerMemory(profile=self._profile(), is_empty=False)
        r = format_customer_memory(memory)
        self.assertIn('CUSTOMER PROFILE', r.profile_text)
        self.assertIn('Alice', r.profile_text)

    def test_no_name_not_shown(self):
        memory = CustomerMemory(profile=self._profile(name=''), is_empty=False)
        self.assertNotIn('- Name:', format_customer_memory(memory).profile_text)

    def test_open_issues_appear(self):
        issue = CustomerIssue(issue_title='Damaged jacket', status='open', priority='high')
        memory = CustomerMemory(profile=self._profile(), open_issues=[issue], is_empty=False)
        r = format_customer_memory(memory)
        self.assertIn('OPEN / RECENT ISSUES', r.open_issues_text)
        self.assertIn('Damaged jacket', r.open_issues_text)

    def test_urgent_issue_flagged(self):
        issue = CustomerIssue(issue_title='Package lost', status='open', priority='urgent')
        memory = CustomerMemory(profile=self._profile(), open_issues=[issue], is_empty=False)
        self.assertIn('[URGENT]', format_customer_memory(memory).open_issues_text)

    def test_high_risk_in_profile(self):
        memory = CustomerMemory(profile=self._profile(), risk_level='HIGH', is_empty=False)
        self.assertIn('HIGH', format_customer_memory(memory).profile_text)

    def test_low_risk_not_shown(self):
        memory = CustomerMemory(profile=self._profile(), risk_level='LOW', is_empty=False)
        self.assertNotIn('Risk Level', format_customer_memory(memory).profile_text)

    def test_context_within_budget(self):
        from app.memory.memory_formatter import MAX_TOTAL_MEMORY_CHARS
        convs = [
            ConversationRecord(intent='order_status', emotion='neutral', customer_message='x' * 300, generated_reply='y' * 300)
            for _ in range(8)
        ]
        issues = [CustomerIssue(issue_title=f'Issue {i}', status='open') for i in range(3)]
        memory = CustomerMemory(profile=self._profile(), recent_conversations=convs, open_issues=issues, is_empty=False)
        r = format_customer_memory(memory)
        self.assertLessEqual(len(r.full_context_text), MAX_TOTAL_MEMORY_CHARS + 50)

    def test_repeat_issue_note(self):
        memory = CustomerMemory(profile=self._profile(), repeat_issue_detected=True, repeat_issue_intent='refund_request', is_empty=False)
        self.assertIn('Repeat inquiry', format_customer_memory(memory).profile_text)


# ---------------------------------------------------------------------------
# Heuristic extraction
# ---------------------------------------------------------------------------
from app.memory.memory_updater import _heuristic_extraction


class TestHeuristicExtraction(unittest.TestCase):

    def test_detects_product(self):
        r = _heuristic_extraction('I want to return my jacket', 'We will process.', 'return_request', 'neutral', 'replied')
        self.assertIn('jacket', r.products_mentioned)

    def test_detects_issue_from_intent(self):
        r = _heuristic_extraction('My package was damaged', 'Sorry.', 'damaged_product', 'angry', 'replied')
        self.assertTrue(r.issue_detected)
        self.assertEqual(r.issue_priority, 'urgent')

    def test_no_issue_for_product_inquiry(self):
        r = _heuristic_extraction('What sizes do running shoes come in?', 'S to XL.', 'product_inquiry', 'neutral', 'replied')
        self.assertFalse(r.issue_detected)

    def test_extracts_name_from_signoff(self):
        r = _heuristic_extraction('Please refund me. Thanks, Priya Sharma', 'Done.', 'refund_request', 'neutral', 'replied')
        self.assertEqual(r.customer_name, 'Priya Sharma')

    def test_name_not_shopifyx(self):
        r = _heuristic_extraction('Thanks, ShopiFyX', '', 'thanks', 'neutral', 'replied')
        self.assertIsNone(r.customer_name)

    def test_resolved_cue_sets_resolved(self):
        r = _heuristic_extraction('Thanks, that worked!', '', 'general_support', 'happy', 'replied')
        self.assertTrue(r.issue_resolved)

    def test_frustrated_sets_high_priority(self):
        r = _heuristic_extraction('Still waiting for my refund!', '', 'refund_status', 'frustrated', 'replied')
        self.assertEqual(r.issue_priority, 'high')

    def test_medium_priority_for_neutral_emotion(self):
        r = _heuristic_extraction('Refund not received', '', 'refund_request', 'neutral', 'replied')
        self.assertEqual(r.issue_priority, 'medium')


# ---------------------------------------------------------------------------
# New customer flow
# ---------------------------------------------------------------------------
class TestNewCustomerFlow(unittest.TestCase):

    def test_new_customer_is_empty(self):
        from app.memory.memory_retriever import retrieve_customer_memory

        with patch('app.memory.memory_retriever.resolve_or_create_customer') as mock_resolve, \
             patch('app.memory.memory_retriever.get_customer_conversations', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_issues', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_interests', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_semantic_interactions', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_relevant_previous_replies', return_value=[]):

            mock_resolve.return_value = CustomerProfile(
                customer_id='new-uuid', email='brandnew@example.com', name='New User', total_interactions=1
            )
            memory = retrieve_customer_memory(
                customer_id='new-uuid',
                customer_email='brandnew@example.com',
                intent='order_status',
                emotion='neutral',
                query_text='Where is my order?',
            )

        self.assertTrue(memory.is_empty)
        self.assertEqual(memory.risk_level, 'LOW')
        self.assertEqual(len(memory.open_issues), 0)

    def test_new_customer_formatted_label(self):
        memory = CustomerMemory(is_empty=True, profile=None)
        r = format_customer_memory(memory)
        self.assertIn('NEW CUSTOMER', r.full_context_text)

    def test_returning_customer_has_history(self):
        from app.memory.memory_retriever import retrieve_customer_memory
        convs = [ConversationRecord(intent='order_status', emotion='neutral', customer_message='Where is my order?')]

        with patch('app.memory.memory_retriever.resolve_or_create_customer') as mock_resolve, \
             patch('app.memory.memory_retriever.get_customer_conversations', return_value=convs), \
             patch('app.memory.memory_retriever.get_customer_issues', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_interests', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_semantic_interactions', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_relevant_previous_replies', return_value=[]):

            mock_resolve.return_value = CustomerProfile(
                customer_id='existing-uuid', email='returning@example.com', name='Returning User', total_interactions=5
            )
            memory = retrieve_customer_memory(
                customer_id='existing-uuid',
                customer_email='returning@example.com',
                intent='order_status',
                emotion='neutral',
                query_text='Where is my order?',
            )

        self.assertFalse(memory.is_empty)
        self.assertEqual(len(memory.recent_conversations), 1)

    def test_high_risk_customer_identified_on_third_email(self):
        '''A customer with open issue + angry emotion should be HIGH risk.'''
        from app.memory.memory_retriever import retrieve_customer_memory
        issues = [CustomerIssue(issue_title='Damaged product', status='open', priority='high')]
        convs = [ConversationRecord(intent='damaged_product', emotion='angry') for _ in range(2)]

        with patch('app.memory.memory_retriever.resolve_or_create_customer') as mock_resolve, \
             patch('app.memory.memory_retriever.get_customer_conversations', return_value=convs), \
             patch('app.memory.memory_retriever.get_customer_issues', return_value=issues) as mock_issues, \
             patch('app.memory.memory_retriever.get_customer_interests', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_semantic_interactions', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_relevant_previous_replies', return_value=[]):

            # Make issues return for both calls (open + resolved)
            mock_issues.return_value = issues

            mock_resolve.return_value = CustomerProfile(
                customer_id='uuid-3', email='angry@example.com', name='Angry User', total_interactions=3
            )
            memory = retrieve_customer_memory(
                customer_id='uuid-3',
                customer_email='angry@example.com',
                intent='damaged_product',
                emotion='angry',
                query_text='My product is still broken!',
            )

        self.assertIn(memory.risk_level, ('HIGH', 'ESCALATE_IMMEDIATELY'))


class TestNeo4jPipelineIntegration(unittest.TestCase):
    '''Verify that Neo4j data flows seamlessly into customer memory and prompt formatting.'''

    def _sample_neo4j_data(self):
        return {
            'customer_found': True,
            'customer': {'id': 'c-100', 'name': 'John Doe', 'email': 'john@example.com', 'tier': 'platinum', 'status': 'active'},
            'orders': [
                {
                    'id': 'o-99',
                    'order_number': 'SFX-9988',
                    'status': 'shipped',
                    'order_date': '2026-09-10',
                    'total_amount': 4999,
                    'products': [{'name': 'Ergonomic Desk Chair', 'sku': 'EDC-01', 'quantity': 1, 'unit_price': 4999}],
                    'shipment': {
                        'status': 'in_transit',
                        'carrier': 'FedEx',
                        'shipped_at': '2026-09-11',
                        'tracking_number': 'FDX-77665544',
                        'estimated_delivery': '2026-09-19',
                        'delivered_at': None,
                    },
                }
            ],
            'previous_conversations': [],
            'issues': [],
            'interests': [],
        }

    def test_retrieve_customer_memory_fetches_and_formats_neo4j(self):
        from app.memory.memory_retriever import retrieve_customer_memory
        sample_data = self._sample_neo4j_data()

        with patch('app.memory.memory_retriever.resolve_or_create_customer') as mock_resolve, \
             patch('app.memory.memory_retriever.get_customer_conversations', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_issues', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_interests', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_semantic_interactions', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_relevant_previous_replies', return_value=[]), \
             patch('app.neo4j_retrieval.get_salesai_context', return_value=sample_data):

            mock_resolve.return_value = CustomerProfile(
                customer_id='c-100', email='john@example.com', name='John Doe', total_interactions=1
            )
            memory = retrieve_customer_memory(
                customer_id='c-100',
                customer_email='john@example.com',
                intent='order_status',
                emotion='neutral',
                query_text='Where is my order SFX-9988?',
            )

        self.assertFalse(memory.is_empty)
        self.assertIsNotNone(memory.graph_context)
        self.assertTrue(memory.graph_context.get('customer_found'))
        self.assertIn('SFX-9988', memory.graph_context_text)
        self.assertIn('FDX-77665544', memory.graph_context_text)
        self.assertIn('FedEx', memory.graph_context_text)

    def test_formatted_memory_context_contains_graph_details(self):
        from app.memory.memory_formatter import format_customer_memory
        from app.neo4j_retrieval import format_graph_context

        sample_data = self._sample_neo4j_data()
        graph_text = format_graph_context(sample_data)

        profile = CustomerProfile(customer_id='c-100', email='john@example.com', name='John Doe', total_interactions=1)
        memory = CustomerMemory(
            profile=profile,
            graph_context=sample_data,
            graph_context_text=graph_text,
            is_empty=False,
        )

        formatted = format_customer_memory(memory, current_intent='order_status', current_message='Hi, where is my order?')
        self.assertIn('GRAPH BUSINESS CONTEXT:', formatted.full_context_text)
        self.assertIn('Order SFX-9988', formatted.full_context_text)
        self.assertIn('tracking=FDX-77665544', formatted.full_context_text)
        self.assertIn('carrier=FedEx', formatted.full_context_text)
        self.assertEqual(formatted.graph_context_text, graph_text)

    def test_neo4j_unconfigured_gracefully_falls_back(self):
        from app.memory.memory_retriever import retrieve_customer_memory
        from app.memory.memory_formatter import format_customer_memory

        with patch('app.memory.memory_retriever.resolve_or_create_customer') as mock_resolve, \
             patch('app.memory.memory_retriever.get_customer_conversations', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_issues', return_value=[]), \
             patch('app.memory.memory_retriever.get_customer_interests', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_semantic_interactions', return_value=[]), \
             patch('app.memory.memory_retriever._retrieve_relevant_previous_replies', return_value=[]), \
             patch('app.neo4j_retrieval.neo4j_client') as mock_client:

            mock_client.configured = False
            mock_resolve.return_value = CustomerProfile(
                customer_id='new-1', email='unconf@example.com', name='Valued Customer', total_interactions=0
            )
            memory = retrieve_customer_memory(
                customer_id='new-1',
                customer_email='unconf@example.com',
                intent='order_status',
                emotion='neutral',
                query_text='Where is my package?',
            )

        self.assertTrue(memory.is_empty)
        formatted = format_customer_memory(memory)
        self.assertIn('[NEW CUSTOMER - No prior history]', formatted.full_context_text)


if __name__ == '__main__':
    unittest.main()
