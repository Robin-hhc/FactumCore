/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05573(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
