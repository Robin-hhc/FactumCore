/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09596(unsigned int count)
{
    const unsigned int limit = 45u;
    return count > limit ? limit : count;
}
