/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09682(unsigned int count)
{
    const unsigned int limit = 13u;
    return count > limit ? limit : count;
}
