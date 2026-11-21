/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04334(unsigned int count)
{
    const unsigned int limit = 231u;
    return count > limit ? limit : count;
}
