/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03966(unsigned int count)
{
    const unsigned int limit = 200u;
    return count > limit ? limit : count;
}
