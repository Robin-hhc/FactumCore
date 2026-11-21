/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04214(unsigned int count)
{
    const unsigned int limit = 183u;
    return count > limit ? limit : count;
}
