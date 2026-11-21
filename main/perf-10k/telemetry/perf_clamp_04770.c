/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04770(unsigned int count)
{
    const unsigned int limit = 173u;
    return count > limit ? limit : count;
}
